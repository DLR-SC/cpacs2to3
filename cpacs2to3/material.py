# Copyright (C) 2013 Deutsches Zentrum fuer Luft- und Raumfahrt(DLR, German Aerospace Center) <www.dlr.de>
"""
documentation
"""
import numpy as np
import numpy.linalg as nplin
from collections import OrderedDict
import logging

from cpacs2to3 import tixi_helper


def upgrade_material_cpacs_31(cpacs_handle):
    """upgrades material definition from cpacs 3.0 to 3.1"""

    # read materials
    base_x_path = '/cpacs/vehicles/materials'
    materials = []
    for xpath in tixi_helper.resolve_xpaths(cpacs_handle, base_x_path + '/material'):
        material = MaterialDefinition()
        material.read_cpacs(xpath, cpacs_handle)
        materials.append(material)

    # add materials as cpacs3.1
    for material in materials:
        material.remove_cpacs2_definitions(cpacs_handle)
        material.write_cpacs(cpacs_handle)


class MaterialDefinition:
    """classdocs"""

    def __init__(self, **kwargs):
        """doc"""
        self.xPath = None
        self.id = None
        self.name = None
        self.description = None
        self.rho = None

        self.stiffnessMatrix = np.zeros((6, 6))
        """stiffnesses of material definition"""

        self.strength = {}
        """Max strength"""
        self._strengthValues = ["sigma11t", "sigma11c", "sigma22t", "sigma22c", "tau12", "tau23"]

        self.strain = {}
        """Max strain"""
        self._strainValues = ["eps11t", "eps11c", "eps22t", "eps22c", "gamma"]

        self.fatiqueFactor = None

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

        self.set_strength(kwargs.pop("strength", dict([(s, 0.0) for s in self._strengthValues])))

    def read_cpacs(self, x_path, tixi):
        """calculations from Altenbach - Einfuehrung in die Mechanik der Laminat- und 
        Sandwichtragwerke; Deutscher Verlag fuer Grundstoffindustrie p.36 cont."""
        self.xPath = x_path
        if tixi.checkAttribute(x_path, "uID"):
            uid = tixi.getTextAttribute(x_path, "uID")
            if uid != "":
                self.id = uid

        if self.id in ["", None]:
            self.id = x_path.rsplit("/", 1)[1]

        self._savedModuli = {}
        self.name = tixi.getTextElement(x_path + "/name")
        self.rho = tixi.getDoubleElement(x_path + "/rho")
        if tixi.checkElement(x_path + "/fatigueFactor"):
            self.fatiqueFactor = tixi.getDoubleElement(x_path + "/fatigueFactor")
        if tixi.checkElement(x_path + "/thermalConductivity"):
            self.thermalConductivity[0] = self.thermalConductivity[3] = self.thermalConductivity[5] = \
                tixi.getDoubleElement(x_path + "/thermalConductivity")
        self.description = ""
        if tixi.checkElement(x_path + "/description"):
            self.description = tixi.getTextElement(x_path + "/description")

        self._read_cpacs_old_directional_properties(x_path, tixi)

        for s in self._strengthValues:
            if abs(self.strength[s]) < 1e-8:
                self.strength[s] = 0.0

        return self

    def _read_cpacs_old_directional_properties(self, x_path, tixi):
        """Read cpacs direction dependend properties. In this case strength and stiffness are read."""
        stiffness_dict = {}

        if tixi.checkElement(x_path + "/k55"):  # required element for orthotropic material
            # orthotropic material
            for stiffEntry in ["k11", "k12", "k13", "k22", "k23", "k33", "k44", "k55", "k66"]:
                stiffness_dict[stiffEntry] = tixi.getDoubleElement(x_path + "/" + stiffEntry)

            sig11t, sig11c, sig22t, sig22c, tau12, tau23 = 1.0, 1.0, 1.0, 1.0, 1.0, 1.0

            warn_msg = (
                    'CPACS reading of strengths for orthotropic material with id "%s" ' % self.id
                    + "is actually not supported - zeros inserted. "
                      "Maybe you intended to create material properties for UD-CFK. "
                      "Then use transversal isotropic material instead!"
            )
            logging.warning(warn_msg)

        else:
            if tixi.checkElement(x_path + "/k23"):  # required element for transversal isotropic material
                # transversal isotropic material
                for stiffEntry in ["k11", "k12", "k22", "k23", "k66"]:
                    stiffness_dict[stiffEntry] = tixi.getDoubleElement(x_path + "/" + stiffEntry)

                sig11t = tixi.getDoubleElement(x_path + "/sig11t")
                sig11c = tixi.getDoubleElement(x_path + "/sig11c")
                sig22t = tixi.getDoubleElement(x_path + "/sig22t")
                sig22c = tixi.getDoubleElement(x_path + "/sig22c")
                tau12 = tixi.getDoubleElement(x_path + "/tau12")
                tau23 = tixi.getDoubleElement(x_path + '/tau23')

            elif tixi.checkElement(x_path + "/k11"):  # required element for isotropic material
                # isotropic material
                for stiffEntry in ["k11", "k12"]:
                    stiffness_dict[stiffEntry] = tixi.getDoubleElement(x_path + "/" + stiffEntry)

                sig11t = tixi.getDoubleElement(x_path + "/sig11")
                tau12 = tixi.getDoubleElement(x_path + "/tau12")

                # creating stiffness params for transversal isotropic material
                stiffness_dict["k22"] = stiffness_dict["k11"]
                stiffness_dict["k23"] = stiffness_dict["k12"]
                stiffness_dict["k66"] = 0.5 * (stiffness_dict["k11"] - stiffness_dict["k12"])

                sig11c, sig22t, sig22c = [sig11t] * 3
                tau23 = tau12
            else:
                logging.error("wrong material definition at xPath " + x_path)
                raise ValueError("wrong material definition at xPath " + x_path)

            # creating stiffness params for orthotropic material
            stiffness_dict["k13"] = stiffness_dict["k12"]
            stiffness_dict["k33"] = stiffness_dict["k22"]
            stiffness_dict["k44"] = 0.5 * (stiffness_dict["k22"] - stiffness_dict["k23"])
            stiffness_dict["k55"] = stiffness_dict["k66"]

        # now each stiffness needed for an orthotropic definition is known
        for i in range(6):
            self.stiffnessMatrix[i, i] = stiffness_dict["k%s%s" % (i + 1, i + 1)]

        self.stiffnessMatrix[0, 2] = stiffness_dict["k13"]
        self.stiffnessMatrix[2, 0] = stiffness_dict["k13"]

        self.stiffnessMatrix[0, 1] = stiffness_dict["k12"]
        self.stiffnessMatrix[1, 0] = stiffness_dict["k12"]

        self.stiffnessMatrix[2, 1] = stiffness_dict["k23"]
        self.stiffnessMatrix[1, 2] = stiffness_dict["k23"]

        self.strength["sigma11t"] = abs(sig11t)
        self.strength["sigma22t"] = abs(sig22t)
        self.strength["sigma11c"] = abs(sig11c)
        self.strength["sigma22c"] = abs(sig22c)
        self.strength["tau12"] = tau12
        self.strength["tau23"] = tau23

    def write_cpacs(self, tixi):
        """write cpacs materials"""

        # Stiffness and strength
        if self.is_isotropic:
            x_path = self.xPath + "/isotropicProperties"
            names_and_values = [("E", self.moduli["e11"]),
                                ("G", self.moduli["g12"]),
                                ("sigc", self.strength.get('sigma11c', None)),
                                ("sigt", self.strength.get('sigma11t', None)),
                                ("tau12", self.strength.get('tau12', None)),
                                ("epsc", self.strength.get('eps11c', None)),
                                ("epst", self.strength.get('eps11t', None)),
                                ("gamma12", self.strength.get('gamma', None)),
                                ("thermalConductivity", self.thermalConductivity[0]),
                                ("thermalExpansionCoeff", self.thermalExpansionCoeff[0]),
                                ("fatigueFactor", self.fatiqueFactor),
                                ]
        else:  # solid definitions not isotrop
            x_path = self.xPath + "/orthotropicSolidProperties"
            names_and_values = [("E1", self.moduli["e11"]),
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
                                ("thermalExpansionCoeff3", self.thermalExpansionCoeff[5])]

        if not self.is_orthotropic:
            x_path = self.xPath + "/anisotropicSolidProperties"
            names_and_values = names_and_values[9:]
            k = self.stiffnessMatrix
            names_and_values = [("C11", k[0, 0]),
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
                               names_and_values + \
                               [("thermalConductivity12", self.thermalConductivity[1]),
                                ("thermalConductivity23", self.thermalConductivity[4]),
                                ("thermalConductivity31", self.thermalConductivity[2]),
                                ("thermalExpansionCoeff12", self.thermalExpansionCoeff[1]),
                                ("thermalExpansionCoeff23", self.thermalExpansionCoeff[4]),
                                ("thermalExpansionCoeff31", self.thermalExpansionCoeff[2])]

        if not tixi.checkElement(x_path):
            tixi.createElement(*x_path.rsplit('/', 1))
        for name, value in names_and_values:
            if value is not None and abs(value) > 1e-8:
                # value must be not None and != zero
                tixi.addTextElement(x_path, name, str(value))

    def set_strength(self, strength):
        """This method is intended to set the strength of the material."""
        self.strength.update(strength)

    def remove_cpacs2_definitions(self, tixi):
        """removes the cpacs2 definitions in the material node at self.xPath"""
        elems_to_remove = ["fatigueFactor",
                           "thermalConductivity",
                           "k11", "k12", "k13", "k22", "k23", "k33", "k44", "k55", "k66",
                           "sig11",
                           "tau12",
                           "sig11yieldT",
                           "sig11yieldC",
                           "sig11t",
                           "sig11c",
                           "sig22t",
                           "sig22c",
                           "sig33t",
                           "sig33c",
                           "tau12",
                           "tau23",
                           "tau13",
                           "sig33t",
                           "sig33c",
                           "maxStrain",
                           "postFailure",
                           ]
        for element in elems_to_remove:
            x_path = self.xPath + '/' + element
            if tixi.checkElement(x_path):
                tixi.removeElement(x_path)

    @property
    def moduli(self):
        """
        calculates moduli

        :return: dict with these keys: e11, e22, e33, g12, g23, g13, nu12, nu21, nu31, nu31, nu23
        """
        if self._savedModuli != {}:
            return self._savedModuli
        stiffness_m = self.stiffnessMatrix
        try:
            compliance_m = np.linalg.inv(stiffness_m)
        except np.linalg.LinAlgError:
            raise ValueError(
                "Please check your material definition! "
                + "Could not calculate compliance matrix of material element at xPath "
                + self.xPath
            )

        e11 = compliance_m[0, 0] ** -1
        e22 = compliance_m[1, 1] ** -1
        e33 = compliance_m[2, 2] ** -1

        g23 = compliance_m[3, 3] ** -1
        g13 = compliance_m[4, 4] ** -1
        g12 = compliance_m[5, 5] ** -1

        nu12 = -compliance_m[1, 0] * e11
        nu21 = -compliance_m[0, 1] * e22
        nu13 = -compliance_m[0, 2] * e11

        nu31 = -compliance_m[2, 0] * e33
        nu23 = -compliance_m[2, 1] * e22
        nu32 = -compliance_m[1, 2] * e33

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
                ("nu13", nu13),
                ("nu31", nu31),
                ("nu23", nu23),
                ("nu32", nu32),
            ]
        )

        return self._savedModuli

    @property
    def is_isotropic(self):
        """:return: True if MaterialDefinition is isotropic. This is calculated by means of the stiffness matrix."""
        return abs(self.stiffnessMatrix[0, 1] - self.stiffnessMatrix[1, 2]) < 1e-8

    @property
    def is_orthotropic(self):
        """:return: True if MaterialDefinition is orthotropic or anisotropic.
            This is calculated by means of the stiffness matrix."""
        return not np.any(self.stiffnessMatrix[3:, :3])
