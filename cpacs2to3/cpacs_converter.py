"""
This tool converts CPACS file from Version 2 to 3.

Currently is does:
 - Adds missing uiDs
 - Changes the version number

Still to be implemented:
 - Geometry of wing structure
"""

import logging

import argparse
import math
import re
from datetime import datetime

import numpy as np
import tigl3.configuration
from OCC.TopoDS import topods
from tigl import tiglwrapper
from tigl3 import tigl3wrapper
from tigl3.configuration import transform_wing_profile_geometry
from tigl3.geometry import get_length
from tixi import tixiwrapper
from tixi3 import tixi3wrapper
from tixi3.tixi3wrapper import Tixi3Exception

import cpacs2to3.tixi_helper as tixihelper
from cpacs2to3.tixi_helper import parent_path, element_name, element_index
from cpacs2to3.uid_generator import uidGenerator


def register_uids(tixi3_handle):
    """
    Gets all elements with uiDs and registers them
    :param tixi3_handle:
    """

    invalid_uids = []
    empty_uid_paths = []

    logging.info ("Registering all uIDs")
    paths = tixihelper.resolve_xpaths(tixi3_handle, "/cpacs/vehicles//*[@uID]")
    for elem in paths:
        uid = tixi3_handle.getTextAttribute(elem, "uID")
        if uid == "":
            empty_uid_paths.append(elem)
        else:
            try:
                uidGenerator.register(uid)
            except RuntimeError:
                invalid_uids.append(uid)

    invalid_uids = list(sorted(set(invalid_uids)))
    return invalid_uids, empty_uid_paths


def change_cpacs_version(tixi3_handle):
    """
    Changes the CPACS Version of the file

    :param tixi3_handle: TiXI 3 handle
    """
    tixi3_handle.updateTextElement("/cpacs/header/cpacsVersion", "3.0")


def add_changelog(tixi3_handle):
    """
    Adds a changelog entry to the cpacs file
    :param tixi3_handle: TiXI 3 handle
    """
    if not tixi3_handle.checkElement("/cpacs/header/updates"):
        tixi3_handle.createElement("/cpacs/header", "updates")

    tixi3_handle.createElement("/cpacs/header/updates", "update")
    n_updates = tixi3_handle.getNamedChildrenCount("/cpacs/header/updates", "update")
    xpath = "/cpacs/header/updates/update[%d]" % n_updates
    tixi3_handle.addTextElement(xpath, "modification", "Converted to cpacs 3.0 using cpacs2to3")
    tixi3_handle.addTextElement(xpath, "creator", "cpacs2to3")
    tixi3_handle.addTextElement(xpath, "timestamp", datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))
    tixi3_handle.addTextElement(xpath, "version", "ver1")
    tixi3_handle.addTextElement(xpath, "cpacsVersion", "3.0")


def add_uid(tixi3, xpath, uid):
    if not tixi3.checkElement(xpath):
        return
    if not tixi3.checkAttribute(xpath, "uID"):
        tixi3.addTextAttribute(xpath, "uID", uid)


def add_missing_uids(tixi3):
    logging.info("Add missing uIDs")
    paths = tixihelper.resolve_xpaths(tixi3, "//transformation")
    for path in paths:
        add_uid(tixi3, path, uidGenerator.create(tixi3, path))
        add_uid(tixi3, path + "/rotation", uidGenerator.create(tixi3, path + "/rotation"))
        add_uid(tixi3, path + "/scaling", uidGenerator.create(tixi3, path + "/scaling"))
        add_uid(tixi3, path + "/translation", uidGenerator.create(tixi3, path + "/translation"))

    def genMassPaths(path):
        return (
            '//' + path + '|' +
            '//' + path + '/location|' +
            '//' + path + '/orientation'
        )

    # add uids to positinings, lowerShells, upperShells, rotorBladeAttachments
    xpath = (
        '//positioning|' +
        '//lowerShell|' +
        '//upperShell|' +
        '//rotorBladeAttachment|' +
        '//ribRotation|' +
        '//reference/point|' +
        '//material/orthotropyDirection|' +
        '//stringerPosition|' +
        '//stringerPosition/alignment|' +
        '//framePosition|' +
        '//framePosition/alignment|' +
        '//trailingEdgeDevice/path/steps/step/innerHingeTranslation|' +
        '//trailingEdgeDevice/path/steps/step/outerHingeTranslation|' +
        '//trailingEdgeDevice/tracks/track|' +
        '//globalBeamProperties/beamCrossSection|' +
        '//globalBeamProperties/beamCOG|' +
        '//globalBeamProperties/beamShearCenter|' +
        '//globalBeamProperties/beamStiffness|' +
        '//sparCell|' +
        genMassPaths('mTOM') + '|' +
        genMassPaths('mZFM') + '|' +
        genMassPaths('mMLM') + '|' +
        genMassPaths('mMRM') + '|' +
        genMassPaths('massDescription')
    )
    try:
        paths = tixihelper.resolve_xpaths(tixi3, xpath)
        for path in paths:
            add_uid(tixi3, path, uidGenerator.create(tixi3, path))
    except Tixi3Exception:
        pass


def add_cpacs_transformation_node(tixi3, element_path):
    """
    Adds a transformation node to the element
    :param tixi3:
    :param element_path:
    :return:
    """

    transformation_path = element_path + "/transformation"
    if tixi3.checkElement(transformation_path) is False:
        logging.info ("Adding transformation node to %s" % element_path)

        def add_trans_sub_node(node_name, x, y, z):
            node_path = transformation_path + "/" + node_name
            tixi3.createElement(transformation_path, node_name)
            add_uid(tixi3, node_path, uidGenerator.create(tixi3, node_path))
            tixi3.addDoubleElement(node_path, "x", x, "%g")
            tixi3.addDoubleElement(node_path, "y", z, "%g")
            tixi3.addDoubleElement(node_path, "z", x, "%g")

        tixi3.createElement(element_path, "transformation")
        add_uid(tixi3, transformation_path, uidGenerator.create(tixi3, transformation_path))

        add_trans_sub_node("scaling", 1., 1., 1.)
        add_trans_sub_node("rotation", 0., 0., 0.)
        add_trans_sub_node("translation", 0., 0., 0.)


def add_transformation_nodes(tixi3):
    xpaths = (
        '//enginePylons/enginePylon'
    )

    paths = tixihelper.resolve_xpaths(tixi3, xpaths)
    for path in paths:
        add_cpacs_transformation_node(tixi3, path)


def findNearestCsOrTedUid(tixi3, xpath):
    """
    Finds the uid of the nearest parent which is a component segment or trailing edge device
    :param tixi3: TiXI 3 handle
    :param xpath: XPath of the element to start the search
    """
    end = [it.end() for it in re.finditer('(componentSegment|trailingEdgeDevice)(\[\d+\])?/', xpath)][-1]
    csOrTedXPath = xpath[:end - 1]
    uid = tixi3.getTextAttribute(csOrTedXPath, 'uID')
    return uid


def convertElementUidToEtaAndUid(tixi3, xpath, elementName):
    """
    Converts an elementUID element to an eta/xsi value and a referenceUID to a wing segment referencing the wing section element from elementUID.
    Removes the elementUID element and adds eta and referenceUID elements with new values
    :param tixi3: TiXI 3 handle
    :param xpath: The xpath of the elementUID element
    :param elementName: Name of the element created at xpath which contains the computed eta and referenceUID elements
    """

    # read and remove elementUid
    elementUid = tixi3.getTextElement(xpath)
    index = element_index(tixi3, xpath)
    tixi3.removeElement(xpath)
    
    # convert
    wingSegments = tixihelper.resolve_xpaths(tixi3, '//wing/segments/segment[./toElementUID[text()=\'' + elementUid + '\']]')
    if len(wingSegments) > 0:
        eta = 1.0
        uid = tixi3.getTextAttribute(wingSegments[0], 'uID')
    else:
        wingSegments = tixihelper.resolve_xpaths(tixi3, '//wing/segments/segment[./fromElementUID[text()=\'' + elementUid + '\']]')
        if len(wingSegments) > 0:
            eta = 0.0
            uid = tixi3.getTextAttribute(wingSegments[0], 'uID')
        else:
            logging.warning ('Failed to find a wing segment referencing the section element with uid' + elementUid + '. Manual correction is necessary')
            eta = 0.0
            uid = 'TODO'
    
    # write eta iso line
    parentXPath = parent_path(xpath)
    tixi3.createElementAtIndex(parentXPath, elementName, index)
    newElementXPath = parentXPath + '/' + elementName
    tixi3.addDoubleElement(newElementXPath, 'eta', eta, '%g')
    tixi3.addTextElement(newElementXPath, 'referenceUID', uid)

def getInnerAndOuterScale(tigl3_h, wingUid, segmentUid):

    mgr = tigl3.configuration.CCPACSConfigurationManager_get_instance()
    config = mgr.get_configuration(tigl3_h._handle.value)

    try:
        wing = config.get_wing(wingUid)
    except:
        logging.warning("Could not find a wing with uid {} in getInnerAndOuterScale.".format(wingUid))
        return None

    try:
        segment = wing.get_segment(segmentUid)
    except:
        logging.warning("Could not find a segment with uid {} in getInnerAndOuterScale.".format(wingUid))
        return None

    wingTransform = wing.get_transformation_matrix()
    innerConnection = segment.get_inner_connection()
    outerConnection = segment.get_outer_connection()
    innerProfileWire = innerConnection.get_profile().get_chord_line_wire()
    outerProfileWire = outerConnection.get_profile().get_chord_line_wire()
    innerChordLineWire = transform_wing_profile_geometry(wingTransform, innerConnection, innerProfileWire)
    outerChordLineWire = transform_wing_profile_geometry(wingTransform, outerConnection, outerProfileWire)
    return get_length(topods.Wire(innerChordLineWire)), get_length(topods.Wire(outerChordLineWire))

def findGuideCurveUsingProfile(tixi2, profileUid):

    # check all guide curves of all fuselages and wings
    for type in ['fuselage', 'wing']:
        xpath = 'cpacs/vehicles/aircraft/model/{}s'.format(type)
        n = tixi2.getNumberOfChilds(xpath)
        for idx in range(0, n):
            xpathSegments = xpath + '/{}[{}]/segments'.format(type, idx + 1)
            nSegments = tixi2.getNumberOfChilds(xpathSegments)
            for segmentIdx in range(0, nSegments):
                xpathGuideCurves = xpathSegments + '/segment[{}]/guideCurves'.format(segmentIdx + 1)
                nCurves = tixi2.getNumberOfChilds(xpathGuideCurves)
                for curveIdx in range(0, nCurves):
                    xpathGuideCurve = xpathGuideCurves + '/guideCurve[{}]'.format(curveIdx + 1)
                    currentProfileUid = tixi2.getTextElement(xpathGuideCurve + '/guideCurveProfileUID')

                    if profileUid == currentProfileUid:
                        return tixi2.getTextAttribute(xpathGuideCurve, 'uID')
    return None

def reverseEngineerGuideCurveProfilePoints(tixi2, tigl2, tigl3, guideCurveUid, nProfilePoints):

    guideCurveXPath = tixi2.uIDGetXPath(guideCurveUid)

    # get start segment and end segment to determine the scale
    segmentXPath = parent_path(parent_path(guideCurveXPath))

    rX = np.zeros([nProfilePoints+2,1])
    rY = np.zeros([nProfilePoints+2,1])
    rZ = np.zeros([nProfilePoints+2,1])

    # check if the guideCurve is on a wing or a fuselage
    if 'wing' in guideCurveXPath:
        wingXPath = parent_path(parent_path(segmentXPath))
        wingUid = tixi2.getTextAttribute(wingXPath, 'uID')
        segmentUid = tixi2.getTextAttribute(segmentXPath, 'uID')

        startScale, endScale = getInnerAndOuterScale(tigl3, wingUid, segmentUid)

        # CAUTION There is no user-defined x-axis in CPACS2 guide curves. We have to make a reasonable guess
        x = [1., 0., 0.]
    elif 'fuselage' in guideCurveXPath:
        fromElementXPath = tixi2.uIDGetXPath(tixi2.getTextElement(segmentXPath + '/fromElementUID'))
        startSectionXPath = parent_path(parent_path(fromElementXPath))
        a = startSectionXPath.rfind('[') + 1
        b = startSectionXPath.rfind(']')
        startSectionIdx = int(startSectionXPath[a:b])

        toElementXPath = tixi2.uIDGetXPath(tixi2.getTextElement(segmentXPath + '/toElementUID'))
        endSectionXPath = parent_path(parent_path(toElementXPath))
        a = endSectionXPath.rfind('[') + 1
        b = endSectionXPath.rfind(']')
        endSectionIdx = int(endSectionXPath[a:b])

        startScale = tigl2.fuselageGetCircumference(1, startSectionIdx, 0) / math.pi
        endScale = tigl2.fuselageGetCircumference(1, endSectionIdx - 1, 1) / math.pi
        # CAUTION There is no user-defined x-axis in CPACS2 guide curves. We have to make a reasonable guess
        x = [0., 0., 1.]
    else:
        logging.error("Guide Curve Conversion is only implemented for fuselage and wing guide curves!")
        return None

    px, py, pz = tigl2.getGuideCurvePoints(guideCurveUid, nProfilePoints+2)

    guideCurvePnts = np.zeros((3, nProfilePoints+2))
    guideCurvePnts[0, :] = px
    guideCurvePnts[1, :] = py
    guideCurvePnts[2, :] = pz

    start = guideCurvePnts[:, 0]
    end   = guideCurvePnts[:,-1]

    z = np.cross(x, end - start)

    znorm = np.linalg.norm(z)
    if abs(znorm) < 1e-10:
        logging.error("Error during guide curve profile point calculation: The last point and the first point seem to coincide!")
        return

    z = z / znorm

    for i in range(0, np.size(guideCurvePnts, 1)):
         current = guideCurvePnts[:,i]

         # orthogonal projection
         ny2 = np.dot(end - start, end - start)
         rY[i] = np.dot(current - start, end - start)/ny2

         scale = (1 - rY[i]) * startScale + rY[i] * endScale
         midPoint = (1 - rY[i]) * start + rY[i] * end

         rX[i] = np.dot(current - midPoint, x) / scale
         rZ[i] = np.dot(current - midPoint, z) / scale

    # post-processing. Remove first and last point
    rX = rX[1:-1]
    rY = rY[1:-1]
    rZ = rZ[1:-1]

    return rX, rY, rZ

def convertGuideCurvePoints(tixi3, tixi2, tigl2, tigl3, keepUnusedProfiles = False):

    xpath = "cpacs/vehicles/profiles/guideCurves"
    if not tixi3.checkElement(xpath):
        return

    logging.info("Adapting guide curve profiles to CPACS 3 definition")

    # rename guideCurveProfiles to guideCurves
    if tixi3.checkElement("cpacs/vehicles/profiles/guideCurveProfiles"):
        tixi3.renameElement("cpacs/vehicles/profiles", "guideCurveProfiles", "guideCurves")

    nProfiles = tixi3.getNumberOfChilds(xpath)
    idx = 0
    while idx < nProfiles:
        idx+=1
        xpathProfile = xpath + '/guideCurveProfile[{}]'.format(idx)
        profileUid = tixi3.getTextAttribute(xpathProfile, 'uID')

        guideCurveUid = findGuideCurveUsingProfile(tixi3, profileUid)

        if guideCurveUid is None:
            # The guide curve profile appears to be unused
            if not keepUnusedProfiles:
                # If we don't need it, let's do some clean up
                logging.info("   Removing unused guide curve profile {}".format(profileUid))
                tixi3.removeElement( xpathProfile )
                idx-=1
                nProfiles-=1
        else:
            # rename x to rX
            if tixi3.checkElement(xpathProfile + "/pointList/x"):
                tixi3.renameElement(xpathProfile + "/pointList", "x", "rX")
            nProfilePoints = tixi3.getVectorSize(xpathProfile + "/pointList/rX")

            rX, rY, rZ = reverseEngineerGuideCurveProfilePoints(tixi2, tigl2, tigl3, guideCurveUid, nProfilePoints)

            tixi3.removeElement(xpathProfile + "/pointList")
            tixi3.createElement(xpathProfile, "pointList")
            tixi3.addFloatVector(xpathProfile + "/pointList", "rX", rX, len(rX), "%g")
            tixi3.addFloatVector(xpathProfile + "/pointList", "rY", rY, len(rY), "%g")
            tixi3.addFloatVector(xpathProfile + "/pointList", "rZ", rZ, len(rZ), "%g")



def convertEtaXsiIsoLines(tixi3):
    """
    Convertes eta/xsi and elementUID values to eta/xsi iso lines
    :param tixi3: TiXI 3 handle
    """

    def convertIsoLineCoords(tixi3, xpath, elementName):
        """
        Convertes a multitude of either eta or xsi values to eta or xsi iso lines
        :param tixi3: TiXI 3 handle
        :param xpath: XPath matching multiple eta or xsi double values
        :param elementName: Name of the new element storing the eta/xsi value in the created iso line. Is either 'eta' or 'xsi'
        """
        for path in tixihelper.resolve_xpaths(tixi3, xpath):
            uid = findNearestCsOrTedUid(tixi3, path)

            # get existing eta/xsi value
            value = tixi3.getDoubleElement(path)

            # recreate element to make sure it's empty and properly formatted
            index = element_index(tixi3, path)
            tixi3.removeElement(path)
            tixi3.createElementAtIndex(parent_path(path), element_name(path), index)

            # add sub elements for eta/xsi iso line
            tixi3.addDoubleElement(path, elementName, value, '%g')
            tixi3.addTextElement(path, 'referenceUID', uid)

    etaXpath = (
        '//track/eta|' +
        '//cutOutProfile/eta|' +
        '//intermediateAirfoil/eta|' +
        '//positioningInnerBorder/eta1|' +
        '//positioningOuterBorder/eta1|' +
        '//positioningInnerBorder/eta2|' +
        '//positioningOuterBorder/eta2|' +
        # TODO: uncomment when TIGL has implemented new RibsPositioning
        #'//ribsPositioning/etaStart|' +
        #'//ribsPositioning/etaEnd|' +
        '//ribExplicitPositioning/etaStart|' +
        '//ribExplicitPositioning/etaEnd|' +
        '//innerBorder/etaLE|' +
        '//outerBorder/etaLE|' +
        '//innerBorder/etaTE|' +
        '//outerBorder/etaTE|' +
        '//position/etaOutside|' +
        '//sparCell/fromEta|' +
        '//sparCell/toEta'
    )
    convertIsoLineCoords(tixi3, etaXpath, 'eta')
    
    xsiXpath = (
        '//stringer/innerBorderXsiLE|' +
        '//stringer/innerBorderXsiTE|' +
        '//stringer/outerBorderXsiLE|' +
        '//stringer/outerBorderXsiTE|' +
        '//innerBorder/xsiLE|' +
        '//outerBorder/xsiLE|' +
        '//innerBorder/xsiTE|' +
        '//outerBorder/xsiTE|' +
        '//position/xsiInside'
    )
    convertIsoLineCoords(tixi3, xsiXpath, 'xsi')
    
    # convert elementUIDs
    # TODO: Uncomment, when TIGL supports new ribs positioning structure
    #for path in get_all_paths_matching(tixi3, '//ribsPositioning/elementStartUID|'):
    #    convertElementUidToEtaAndUid(tixi3, path, 'etaStart')
    #for path in get_all_paths_matching(tixi3, '//ribsPositioning/elementEndUID|'):
    #    convertElementUidToEtaAndUid(tixi3, path, 'etaEnd')

def convertEtaXsiRelHeightPoints(tixi3):
    """
    Converts all spar positions to etaXsiRelHeightPoints containing eta, xsi and referenceUID
    :param tixi3: TiXI 3 handle
    """

    # TODO: uncomment when TiGL supports new spar positioning structure
    # convertSparPositions(tixi3)# convert non-explicit stringer

    for path in tixihelper.resolve_xpaths(tixi3, '//lowerShell/stringer|//upperShell/stringer|//cell/stringer'):
        if not tixi3.checkElement(path + '/pitch'):
            continue
    
        # get existing xsi value, if it exists
        xsi = 0.0
        if tixi3.checkElement(path + '/xsi'):
            xsi = tixi3.getDoubleElement(path + '/xsi')
            tixi3.removeElement(path + '/xsi')

        # get existing eta value, if it exists
        eta = 0.0
        if tixi3.checkElement(path + '/eta'):
            eta = tixi3.getDoubleElement(path + '/eta')
            tixi3.removeElement(path + '/eta')

        uid = findNearestCsOrTedUid(tixi3, path)

        # add sub elements for rel height point
        tixi3.createElement(path, 'refPoint')
        path = path + '/refPoint'
        tixi3.addDoubleElement(path, 'eta', eta, '%g')
        tixi3.addDoubleElement(path, 'xsi', xsi, '%g')
        tixi3.addTextElement(path, 'referenceUID', uid)


def convertSparPositions(tixi3):

    # convert sparPosition
    for path in tixihelper.resolve_xpaths(tixi3, '//sparPosition'):
        # get existing xsi value
        xsi = tixi3.getDoubleElement(path + '/xsi')
        tixi3.removeElement(path + '/xsi')

        if tixi3.checkElement(path + '/eta'):
            # if we have an eta, get it
            eta = tixi3.getDoubleElement(path + '/eta')
            tixi3.removeElement(path + '/eta')

            uid = findNearestCsOrTedUid(tixi3, path)

            # add sub elements for rel height point
            tixi3.createElement(path, 'sparPoint')
            path = path + '/sparPoint'
            tixi3.addDoubleElement(path, 'eta', eta, '%g')
            tixi3.addDoubleElement(path, 'xsi', xsi, '%g')
            tixi3.addTextElement(path, 'referenceUID', uid)
        else:
            # in case of elementUID, find wing segment which references the element and convert to eta
            convertElementUidToEtaAndUid(tixi3, path + '/elementUID', 'sparPoint')
            tixi3.addDoubleElement(path + '/sparPoint', 'xsi', xsi, '%g')


def get_new_cs_coordinates(tigl2, tigl3, compseg_uid, eta_old, xsi_old):
    px, py, pz = tigl2.wingComponentSegmentGetPoint(compseg_uid, eta_old, xsi_old)
    return tigl3.wingComponentSegmentPointGetEtaXsi(compseg_uid, px, py, pz)


def main():
    logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG)

    parser = argparse.ArgumentParser(description='Converts a CPACS file from Version 2 to Version 3.')
    parser.add_argument('input_file', help='Input CPACS 2 file')
    parser.add_argument('-o', metavar='output_file', help='Name of the output file.')
    parser.add_argument('--fix-invalid-uids', '-f', help='fix empty and duplicate uids',  action="store_true")

    args = parser.parse_args()
    do_fix_uids = args.fix_invalid_uids

    old_cpacs_file = tixiwrapper.Tixi()
    new_cpacs_file = tixi3wrapper.Tixi3()


    filename = args.input_file
    output_file = args.o

    new_cpacs_file.open(filename)
    new_cpacs_file.setCacheEnabled(1)
    # new_cpacs_file.usePrettylogging.info(1)

    invalid_uids, empty_uids = register_uids(new_cpacs_file)
    if len(invalid_uids) + len(empty_uids) > 0  and do_fix_uids:
        tixihelper.fix_invalid_uids(empty_uids, invalid_uids, new_cpacs_file)

        logging.info("A fixed cpacs2 file will be stored to '%s'" % (filename + ".fixed"))
        fixed_cpacs_str = new_cpacs_file.exportDocumentAsString()
        with open(filename + ".fixed", "w") as text_file:
            text_file.write(fixed_cpacs_str)
    else:
        fixed_cpacs_str = new_cpacs_file.exportDocumentAsString()

    old_cpacs_file.openString(fixed_cpacs_str)

    # perform structural changes
    change_cpacs_version(new_cpacs_file)
    add_missing_uids(new_cpacs_file)
    add_transformation_nodes(new_cpacs_file)
    convertEtaXsiIsoLines(new_cpacs_file)
    convertEtaXsiRelHeightPoints(new_cpacs_file)
    add_changelog(new_cpacs_file)


    tigl2 = tiglwrapper.Tigl()
    tigl2.open(old_cpacs_file, "")

    tigl3 = tigl3wrapper.Tigl3()
    tigl3.open(new_cpacs_file, "")

    convertGuideCurvePoints(new_cpacs_file, old_cpacs_file, tigl2, tigl3)

    logging.info ("Done")

    if output_file is not None:
        new_cpacs_file.save(output_file)
    else:
        logging.info(new_cpacs_file.exportDocumentAsString())



if __name__ == "__main__":
    main()
