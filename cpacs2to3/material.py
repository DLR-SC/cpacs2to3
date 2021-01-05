# Copyright (C) 2013 Deutsches Zentrum fuer Luft- und Raumfahrt(DLR, German Aerospace Center) <www.dlr.de>
"""
documentation
"""
import numpy as np
import numpy.linalg as nplin
from scipy.linalg import block_diag
from collections import OrderedDict
import logging as log

from cpacs2to3 import tixi_helper


def upgradeMaterialCpacs31(cpacs_handle):
    """upgrades material definition from cpacs 3.0 to 3.1 by rewriting the material entries"""

    # read materials
    baseXPath = '/cpacs/vehicles/materials'
    materials = []
    for xpath in tixi_helper.resolve_xpaths(cpacs_handle, baseXPath + '/material'):
        material = MaterialDefinition()
        material.readCpacs(xpath, cpacs_handle)
        materials.append(material)

    # remove and recreate material branch
    cpacs_handle.removeElement(baseXPath)
    cpacs_handle.addTextElement(*tixi_helper.split_parent_child_path(baseXPath), '')

    # add materials as cpacs3.1
    for material in materials:
        cpacs_handle.addTextElement(*tixi_helper.split_parent_child_path(material.xPath), '')
        material.writeCpacs(cpacs_handle)


class MaterialDefinition():
    """classdocs"""

    def __init__(self, **kwargs):
        """doc"""
        self.xPath = None
        self.id = None
        self.name = None
        self.description = None
        self.rho = None

        self.isShell = False
        """Flag if shell properties are given. Required for cpacs writing"""

        self.stiffnessMatrix = np.zeros((6, 6))
        """stiffnesses of material definition"""

        self.strength = {}
        """Max strength"""
        self._strengthValues = ["sigma11t", "sigma11c", "sigma22t", "sigma22c", "tau"]

        self.strain = {}
        """Max strain"""
        self._strainValues = ["eps11t", "eps11c", "eps22t", "eps22c", "gamma"]

        self._savedModuli = {}

        self._kPlaneStressCondition = None
        """3x3 matrix containing the plane stress stiffnesses.
        calculated according to altenberg page 53. The z-direction is the out of
        plane direction with sigma_z = 0 and so on."""

        self.usedAngles = set()
        """Angles as integer in degrees which represent the orientations that 
        are used with this materialDefinition. 
        It is set within Layer.materialDefinition and is needed to create rotated
        materialDefinitions for complex cross sections"""

        self.thermalConductivity = np.zeros((6,))
        """Thermal conductivity KXX KXY KXZ KYY KYZ KZZ"""

        self.thermalExpansionCoeff = np.zeros((6,))
        """Thermal expansion coefficient in the 3 directions XX XY XZ YY YZ ZZ"""

        self.thermalExpansionCoeffTemp = 20 + 273.15
        """Reference temperature for thermalExpansionCoeff"""

        self.specificHeats = None
        """Specific heat capacity sample points of the material in [J/(kg*K)].
        Vector with at least len=2"""

        self.specificHeatTemperatures = None
        """Temperatures to the specific heat capacities
        Vector with at least len=2"""

        self.specificHeatDefaultTemp = 20 + 273.15
        """Default temperature for specificHeat"""

        self.setStrength(kwargs.pop("strength", dict([(s, 0.0) for s in self._strengthValues])))

        for key in kwargs:
            if not hasattr(self, key):
                log.warning('Setting unknown key "%s" in class %s with name "%s"' % (key, self.__class__, str(self)))
            setattr(self, key, kwargs[key])

    def readCpacs(self, xPath, tixi):
        """calculations from Altenbach - Einfuehrung in die Mechanik der Laminat- und 
        Sandwichtragwerke; Deutscher Verlag fuer Grundstoffindustrie p.36 cont."""
        self.xPath = xPath
        if tixi.checkAttribute(xPath, "uID"):
            uid = tixi.getTextAttribute(xPath, "uID")
            if uid != "":
                self.id = uid

        if self.id in ["", None]:
            self.id = xPath.rsplit("/", 1)[1]
            
        self._savedModuli = {}
        self.name = tixi.getTextElement(xPath + "/name")
        self.rho = tixi.getDoubleElement(xPath + "/rho")

        self.description = ""
        if tixi.checkElement(xPath + "/description"):
            self.description = tixi.getTextElement(xPath + "/description")

        if tixi.checkElement(xPath + "/referenceTemperature"):
            self.thermalExpansionCoeffTemp = tixi.getDoubleElement(xPath + "/referenceTemperature")

        self._readCpacsOldDirectionalProperties(xPath, tixi)

        for s in self._strengthValues:
            if abs(self.strength[s]) < 1e-8:
                self.strength[s] = 0.0

        return self

    def _readCpacsOldDirectionalProperties(self, xPath, tixi):
        """Read cpacs direction dependend properties. In this case strength and stiffness are read."""
        stiffnessDict = {}

        if tixi.checkElement(xPath + "/k55"):  # required element for orthotrop material
            # orthotrop material
            for stiffEntry in ["k11", "k12", "k13", "k22", "k23", "k33", "k44", "k55", "k66"]:
                stiffnessDict[stiffEntry] = tixi.getDoubleElement(xPath + "/" + stiffEntry)

            sig11t, sig11c, sig22t, sig22c, tau12 = 1.0, 1.0, 1.0, 1.0, 1.0

            warnMsg = (
                'CPACS reading of strengths for orthotrop material with id "%s" ' % self.id
                + "is actually not supported - zeros inserted. "
                "Maybe you intended to create material properties for UD-CFK. "
                "Then use transversal isotrop material instead!"
            )
            log.warning(warnMsg)

        else:
            if tixi.checkElement(xPath + "/k23"):  # required element for transversal isotrop material
                # transversal isotrop material
                for stiffEntry in ["k11", "k12", "k22", "k23", "k66"]:
                    stiffnessDict[stiffEntry] = tixi.getDoubleElement(xPath + "/" + stiffEntry)

                sig11t = tixi.getDoubleElement(xPath + "/sig11t")
                sig11c = tixi.getDoubleElement(xPath + "/sig11c")
                sig22t = tixi.getDoubleElement(xPath + "/sig22t")
                sig22c = tixi.getDoubleElement(xPath + "/sig22c")
                tau12 = tixi.getDoubleElement(xPath + "/tau12")
                # tau23 = tixi.getDoubleElement(xPath + '/tau23')

            elif tixi.checkElement(xPath + "/k11"):  # required element for isotrop material
                # isotrop material
                for stiffEntry in ["k11", "k12"]:
                    stiffnessDict[stiffEntry] = tixi.getDoubleElement(xPath + "/" + stiffEntry)

                sig11t = tixi.getDoubleElement(xPath + "/sig11")
                tau12 = tixi.getDoubleElement(xPath + "/tau12")

                # creating stiffness params for transversal isotrop material
                stiffnessDict["k22"] = stiffnessDict["k11"]
                stiffnessDict["k23"] = stiffnessDict["k12"]
                stiffnessDict["k66"] = 0.5 * (stiffnessDict["k11"] - stiffnessDict["k12"])

                sig11c, sig22t, sig22c = [sig11t] * 3
                # tau23 = tau12
            else:
                raise ValueError("wrong material definition at xPath " + xPath)

            # creating stiffness params for orthotrop material
            stiffnessDict["k13"] = stiffnessDict["k12"]
            stiffnessDict["k33"] = stiffnessDict["k22"]
            stiffnessDict["k44"] = 0.5 * (stiffnessDict["k22"] - stiffnessDict["k23"])
            stiffnessDict["k55"] = stiffnessDict["k66"]

        # now each stiffness needed for an orthotrop definition is known
        for i in range(6):
            self.stiffnessMatrix[i, i] = stiffnessDict["k%s%s" % (i + 1, i + 1)]

        self.stiffnessMatrix[0, 2] = stiffnessDict["k13"]
        self.stiffnessMatrix[2, 0] = stiffnessDict["k13"]

        self.stiffnessMatrix[0, 1] = stiffnessDict["k12"]
        self.stiffnessMatrix[1, 0] = stiffnessDict["k12"]

        self.stiffnessMatrix[2, 1] = stiffnessDict["k23"]
        self.stiffnessMatrix[1, 2] = stiffnessDict["k23"]

        self.strength["sigma11t"] = abs(sig11t)
        self.strength["sigma22t"] = abs(sig22t)
        self.strength["sigma11c"] = abs(sig11c)
        self.strength["sigma22c"] = abs(sig22c)
        self.strength["tau"] = tau12


    def writeCpacs(self, tixi):
        """write cpacs materials"""
        tixi.addTextAttribute(self.xPath, "uID", self.id)
        tixi.addTextElement(self.xPath, 'name', self.name)
        if self.description:
            tixi.addTextElement(self.xPath, "description", self.description)
        tixi.addTextElement(self.xPath, 'rho', str(self.rho))
        if np.any(self.thermalExpansionCoeff):
            tixi.addTextElement(self.xPath, 'referenceTemperature', str(self.thermalExpansionCoeffTemp))

        # Stiffness and strength
        if self.isIsotrop:
            xPath = self.xPath + "/isotropicProperties"
            namesAndValues = [("E", self.moduli["e11"]),
                              ("G", self.moduli["g12"]),
                              ("sigc", self.strength.get('sigma11c', None)),
                              ("sigt", self.strength.get('sigma11t', None)),
                              ("tau12", self.strength.get('tau', None)),
                              ("epsc", self.strength.get('eps11c', None)),
                              ("epst", self.strength.get('eps11t', None)),
                              ("gamma12", self.strength.get('gamma', None)),
                              ("thermalConductivity", self.thermalConductivity[0]),
                              ("thermalExpansionCoeff", self.thermalExpansionCoeff[0]),]
        elif self.isShell: # shells not isotrop
            xPath = self.xPath + "/orthotropicShellProperties"
            namesAndValues = [("E1", self.moduli["e11"]),
                              ("E2", self.moduli["e22"]),
                              ("G12", self.moduli["g12"]),
                              ("nu", self.moduli["nu12"]),
                              ("sig1c", self.strength.get('sigma11c', None)),
                              ("sig1t", self.strength.get('sigma11t', None)),
                              ("sig2c", self.strength.get('sigma22c', None)),
                              ("sig2t", self.strength.get('sigma22t', None)),
                              ("tau12", self.strength.get('tau', None)),
                              ("eps1c", self.strength.get('eps11c', None)),
                              ("eps1t", self.strength.get('eps11t', None)),
                              ("eps2c", self.strength.get('eps22c', None)),
                              ("eps2t", self.strength.get('eps22t', None)),
                              ("gamma12", self.strength.get('gamma', None)),
                              ("thermalConductivity1", self.thermalConductivity[0]),
                              ("thermalConductivity2", self.thermalConductivity[3]),
                              ("thermalExpansionCoeff1", self.thermalExpansionCoeff[0]),
                              ("thermalExpansionCoeff2", self.thermalExpansionCoeff[3]),]
        else: # solid definitions not isotrop
            xPath = self.xPath + "/orthotropicSolidProperties"
            namesAndValues = [("E1", self.moduli["e11"]),
                              ("E2", self.moduli["e22"]),
                              ("E3", self.moduli["e33"]),
                              ("G12", self.moduli["g12"]),
                              ("G23", self.moduli["g23"]),
                              ("G31", self.moduli["g13"]),
                              ("nu12", self.moduli["nu12"]),
                              ("nu23", self.moduli["nu23"]),
                              ("nu31", self.moduli["nu31"]),
                              ("sig1c", self.strength.get('sigma11c', None)),
                              ("sig1t", self.strength.get('sigma11t', None)),
                              ("sig2c", self.strength.get('sigma22c', None)),
                              ("sig2t", self.strength.get('sigma22t', None)),
                              ("sig3c", self.strength.get('sigma33c', None)),
                              ("sig3t", self.strength.get('sigma33t', None)),
                              ("tau12", self.strength.get('tau12', None)),
                              ("tau23", self.strength.get('tau23', None)),
                              ("tau31", self.strength.get('tau31', None)),
                              ("eps1c", self.strength.get('eps11c', None)),
                              ("eps1t", self.strength.get('eps11t', None)),
                              ("eps2c", self.strength.get('eps22c', None)),
                              ("eps2t", self.strength.get('eps22t', None)),
                              ("eps3c", self.strength.get('eps33c', None)),
                              ("eps3t", self.strength.get('eps33t', None)),
                              ("gamma12", self.strength.get('gamma12', None)),
                              ("gamma23", self.strength.get('gamma23', None)),
                              ("gamma31", self.strength.get('gamma31', None)),
                              ("thermalConductivity1", self.thermalConductivity[0]),
                              ("thermalConductivity2", self.thermalConductivity[3]),
                              ("thermalConductivity3", self.thermalConductivity[5]),
                              ("thermalExpansionCoeff1", self.thermalExpansionCoeff[0]),
                              ("thermalExpansionCoeff2", self.thermalExpansionCoeff[3]),
                              ("thermalExpansionCoeff3", self.thermalExpansionCoeff[5]),]

        if self.isShell and not self.isOrthotrop:
            xPath = self.xPath + "/anisotropicShellProperties"
            namesAndValues = namesAndValues[4:]
            Q = self.getReducedStiffnessMatrix()
            namesAndValues = [("Q11", Q[0, 0]),
                              ("Q12", Q[0, 1]),
                              ("Q13", Q[0, 2]),
                              ("Q22", Q[1, 1]),
                              ("Q23", Q[1, 2]),
                              ("Q33", Q[2, 2]),] + \
                             namesAndValues + \
                             [("thermalConductivity3", self.thermalConductivity[5]),
                              ("thermalExpansionCoeff12", self.thermalExpansionCoeff[1]),]

        if not self.isShell and not self.isOrthotrop:
            xPath = self.xPath + "/anisotropicSolidProperties"
            namesAndValues = namesAndValues[9:]
            k = self.stiffnessMatrix
            namesAndValues = [("C11", k[0, 0]),
                              ("C12", k[0, 1]),
                              ("C13", k[0, 2]),
                              ("C14", k[0, 3]),
                              ("C15", k[0, 4]),
                              ("C16", k[0, 5]),
                              ("C22", k[1, 1]),
                              ("C23", k[1, 2]),
                              ("C24", k[1, 3]),
                              ("C25", k[1, 4]),
                              ("C26", k[1, 5]),
                              ("C33", k[2, 2]),
                              ("C34", k[2, 3]),
                              ("C35", k[2, 4]),
                              ("C36", k[2, 5]),
                              ("C44", k[3, 3]),
                              ("C45", k[3, 4]),
                              ("C46", k[3, 5]),
                              ("C55", k[4, 4]),
                              ("C56", k[4, 5]),
                              ("C66", k[5, 5]),
                              ] + \
                             namesAndValues + \
                             [("thermalConductivity12", self.thermalConductivity[1]),
                              ("thermalConductivity23", self.thermalConductivity[4]),
                              ("thermalConductivity31", self.thermalConductivity[2]),
                              ("thermalExpansionCoeff12", self.thermalExpansionCoeff[1]),
                              ("thermalExpansionCoeff23", self.thermalExpansionCoeff[4]),
                              ("thermalExpansionCoeff31", self.thermalExpansionCoeff[2]),]

        if not tixi.checkElement(xPath):
            tixi.createElement(*xPath.rsplit('/',1))
        for name, value in namesAndValues:
            if value is not None and abs(value)>1e-8:
                # value must be not None and != zero
                tixi.addTextElement(xPath, name, str(value))
        return

    def setStiffnessMatrix(
        self,
        # isotrop
        e1,
        g12,
        # transversal isotrop
        e2=None,
        nu12=None,
        nu23=None,
        # orthotrop
        e3=None,
        g23=None,
        g13=None,
        nu31=None,
    ):
        """This method assumes a transverse isotropic material.

        Altenbach, Holm, Johannes Altenbach, und Rolands Rikards.
            Einführung in die Mechanik der Laminat- und Sandwichtragwerke:
            Modellierung und Berechnung von Balken und Platten aus Verbundwerkstoffen.
            1. Aufl. Stuttgart: Wiley-VCH, 1996.

            page 45 (Transversale Isotropie)

        Accepted parameter combinations:

        - isotrop
            - e1, g12
            - e1, nu12
        - transversal isotrop
            - e1, g12, e2, nu12
            - e1, g12, e2, nu12, nu23
            - e1, g12, e2, nu12, nu23, g23, g13
        - orthotrop
            - e1, g12, e2, nu12, nu23, e3, g23, g13, nu31
        """

        if g12 is None:
            # isotrop switch if e and nu are given
            g12 = e1 / (2 * (1 + nu12))

        if not all(np.array([e2, nu12]) != None):
            log.debug(f"Isotrop behavior material assumed for material with id {self.id}")
            e2 = e3 = e1
            nu12 = e1 / 2 / g12 - 1
            nu31 = nu23 = nu12
            g13 = g23 = g12
        elif not all(np.array([e3, g23, g13, nu31]) != None):
            log.debug(f"Transversal isotrop material behavior assumed for material with id {self.id}")
            e3 = e2
            nu31 = nu12
            g13 = g12 if g13 is None else g13
            nu23 = nu12 if nu23 is None else nu23
            g23 = e2 / (2.0 * (1 + nu23)) if g23 is None else g23
        else:
            log.debug(f"Orthotrop material behavior assumed for material with id {self.id}")

        self._savedModuli = {}

        matUpperLeft = np.array(
            [
                [1.0 / e1, -nu12 / e1, -nu31 / e1],
                [-nu12 / e1, 1.0 / e2, -nu23 / e2],
                [-nu31 / e1, -nu23 / e2, 1.0 / e3,],
            ]
        )

        matLowerRight = np.diag([1.0 / g23, 1.0 / g13, 1.0 / g12])

        compliance = block_diag(matUpperLeft, matLowerRight)
        self.stiffnessMatrix = np.linalg.inv(compliance)

    def setStrength(self, strength):
        """This method is intended to set the strength of the material."""
        self.strength.update(strength)

    def _getModuli(self):
        """
        calculates moduli

        :return: dict with these keys: e11, e22, e33, g12, g23, g13, nu12, nu21, nu31, nu31, nu23
        """
        if self._savedModuli != {}:
            return self._savedModuli
        stiffnessM = self.stiffnessMatrix
        try:
            complianceM = np.linalg.inv(stiffnessM)
        except np.linalg.LinAlgError:
            raise ValueError(
                "Please check your material definition! "
                + "Could not calculate compliance matrix of material element at xPath "
                + self.xPath
            )

        e11 = complianceM[0, 0] ** -1
        e22 = complianceM[1, 1] ** -1
        e33 = complianceM[2, 2] ** -1

        g23 = complianceM[3, 3] ** -1
        g13 = complianceM[4, 4] ** -1
        g12 = complianceM[5, 5] ** -1

        nu12 = -complianceM[1, 0] * e11
        nu21 = -complianceM[0, 1] * e22
        nu31 = -complianceM[0, 2] * e33

        nu31 = -complianceM[2, 0] * e11
        nu23 = -complianceM[2, 1] * e22
        nu32 = -complianceM[1, 2] * e33

        if any(value < 0 for value in [e11, e22, e33, g12, g23, g13]):
            if not hasattr(self, "xPath"):
                self.xPath = ""
            raise ValueError(
                "Please check your material definition! "
                + "Got negative youngs- or shear modulus at material element at xPath "
                + self.xPath
            )

        self._savedModuli = OrderedDict(
            [
                ("e11", e11),
                ("e22", e22),
                ("e33", e33),
                ("g12", g12),
                ("g23", g23),
                ("g13", g13),
                ("nu12", nu12),
                ("nu21", nu21),
                ("nu31", nu31),
                ("nu31", nu31),
                ("nu23", nu23),
                ("nu32", nu32),
            ]
        )

        return self._savedModuli

    def _getIsIsotrop(self):
        """:return: True if MaterialDefinition is isotrop. This is calculated by means of the stiffness matrix."""
        return abs(self.stiffnessMatrix[0, 1] - self.stiffnessMatrix[1, 2]) < 1e-8

    def _getIsOrthotrop(self):
        """:return: True if MaterialDefinition is orthotrop. This is calculated by means of the stiffness matrix."""
        return not np.any(self.stiffnessMatrix[3:, :3])

    moduli = property(fget=_getModuli)
    isIsotrop = property(fget=_getIsIsotrop)
    isOrthotrop = property(fget=_getIsOrthotrop)


