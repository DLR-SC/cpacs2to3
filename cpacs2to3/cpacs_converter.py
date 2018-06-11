"""
This tool converts CPACS file from Version 2 to 3.

Currently is does:
 - Adds missing uiDs
 - Changes the version number

Still to be implemented:
 - Geometry of wing structure
"""

from __future__ import print_function

import argparse
import re
import math
import numpy as np

from tigl import tiglwrapper
from tigl3 import tigl3wrapper

from tixi3 import tixi3wrapper
from tixi3.tixi3wrapper import Tixi3Exception
from tixi import tixiwrapper

from datetime import datetime


class UIDGenerator(object):
    def __init__(self):
        self.counter = 0
        self.uids = set()

    def create(self, tixi_handle, current_path):
        parent, elem = get_parent_child_path(current_path)
        while not tixi_handle.checkAttribute(parent, "uID"):
            parent, _ = get_parent_child_path(parent)

        parent_uid = tixi_handle.getTextAttribute(parent, "uID")

        counter = 1
        new_uid = "%s_%s%d" % (parent_uid, elem, counter)
        while self.uid_exists(new_uid):
            counter += 1
            new_uid = "%s_%s%d" % (parent_uid, elem, counter)

        self.register(new_uid)
        return new_uid

    def register(self, uid):
        """
        Register an existing uid at the generator
        This is, to make sure this uid won't generated
        to avoid duplication of UIDs.
        :param uid:
        """
        self.uids.add(uid)

    def uid_exists(self, uid):
        return uid in self.uids


uidGenerator = UIDGenerator()


def register_uids(tixi3_handle):
    """
    Gets all elements with uiDs and registers them
    :param tixi3_handle:
    """
    print ("Registering all uIDs")
    paths = get_all_paths_matching(tixi3_handle, "//*[@uID]")
    for elem in paths:
        uid = tixi3_handle.getTextAttribute(elem, "uID")
        uidGenerator.register(uid)


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


def get_all_paths_matching(tixi3, xpath):
    try:
        n_nodes = tixi3.xPathEvaluateNodeNumber(xpath)
        paths = []
        for i in range(0, n_nodes):
            paths.append(tixi3.xPathExpressionGetXPath(xpath, i+1))
        return paths
    except Tixi3Exception:
        return []


def add_uid(tixi3, xpath, uid):
    if not tixi3.checkElement(xpath):
        return
    if not tixi3.checkAttribute(xpath, "uID"):
        tixi3.addTextAttribute(xpath, "uID", uid)


def add_missing_uids(tixi3):
    print("Add missing uIDs")
    paths = get_all_paths_matching(tixi3, "//transformation")
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
        genMassPaths('mTOM') + '|' +
        genMassPaths('mZFM') + '|' +
        genMassPaths('mMLM') + '|' +
        genMassPaths('mMRM') + '|' +
        genMassPaths('massDescription')
    )
    try:
        paths = get_all_paths_matching(tixi3, xpath)
        for path in paths:
            add_uid(tixi3, path, uidGenerator.create(tixi3, path))
    except Tixi3Exception:
        pass

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


def childElement(xpath):
    """
    Gives the last element in an xpath
    :param xpath: An xpath with at least one '/'
    """
    return xpath[xpath.rfind('/') + 1:]


def parentPath(xpath):
    """
    Removes the last element in an xpath, effectively yielding the xpath to the parent element
    :param xpath: An xpath with at least one '/'
    """
    return xpath[:xpath.rfind('/')]


def elementIndexInParent(tixi3, xpath):
    """
    Finds the index of the child element in the given xpath in its parent element
    :param tixi3: TiXI 3 handle
    :param xpath: An xpath with at least one '/'
    """
    parentXPath = parentPath(xpath)
    childName = childElement(xpath)
    count = tixi3.getNumberOfChilds(parentXPath)
    for i in range(count):
        if tixi3.getChildNodeName(parentXPath, i + 1) == childName:
            return i + 1
    return count

    
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
    index = elementIndexInParent(tixi3, xpath)
    tixi3.removeElement(xpath)
    
    # convert
    wingSegments = get_all_paths_matching(tixi3, '//wing/segments/segment[./toElementUID[text()=\'' + elementUid + '\']]')
    if len(wingSegments) > 0:
        eta = 1.0
        uid = tixi3.getTextAttribute(wingSegments[0], 'uID')
    else:
        wingSegments = get_all_paths_matching(tixi3, '//wing/segments/segment[./fromElementUID[text()=\'' + elementUid + '\']]')
        if len(wingSegments) > 0:
            eta = 0.0
            uid = tixi3.getTextAttribute(wingSegments[0], 'uID')
        else:
            print ('Failed to find a wing segment referencing the section element with uid' + elementUid + '. Manual correction is necessary')
            eta = 0.0
            uid = 'TODO'
    
    # write eta iso line
    parentXPath = parentPath(xpath)
    tixi3.createElementAtIndex(parentXPath, elementName, index)
    newElementXPath = parentXPath + '/' + elementName
    tixi3.addDoubleElement(newElementXPath, 'eta', eta, '%g')
    tixi3.addTextElement(newElementXPath, 'referenceUID', uid)

def getChordLength(tigl3, sectionUid):
    #TODO
    return 1.

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

    print("   Could not find a guide curve referencing the profile with uid {}".format(profileUid))
    return None

def reverseEngineerGuideCurveProfilePoints(tixi2, tigl2, tigl3, guideCurveUid, nProfilePoints):

    guideCurveXPath = tixi2.uIDGetXPath(guideCurveUid)

    # get start segment and end segment to determine the scale
    segmentXPath = parentPath(parentPath(guideCurveXPath))

    fromElementXPath = tixi2.uIDGetXPath(tixi2.getTextElement(segmentXPath + '/fromElementUID'))
    startSectionXPath = parentPath(parentPath(fromElementXPath))
    a = startSectionXPath.rfind('[') + 1
    b = startSectionXPath.rfind(']')
    startSectionIdx = int(startSectionXPath[a:b])

    toElementXPath = tixi2.uIDGetXPath(tixi2.getTextElement(segmentXPath + '/toElementUID'))
    endSectionXPath = parentPath(parentPath(toElementXPath))
    a = endSectionXPath.rfind('[') + 1
    b = endSectionXPath.rfind(']')
    endSectionIdx = int(endSectionXPath[a:b])

    rX = np.zeros([nProfilePoints+2,1])
    rY = np.zeros([nProfilePoints+2,1])
    rZ = np.zeros([nProfilePoints+2,1])

    # check if the guideCurve is on a wing or a fuselage
    if 'wing' in guideCurveXPath:
        print('   It\'s a wing! The start and end scales are not calculated correctly yet')
        # TODO startScale, endScale is innerChordlineLength and outerChordLineLength
        startScale = getChordLength(tigl3, startSectionIdx)
        endScale = getChordLength(tigl3, endSectionIdx)

        # CAUTION There is no user-defined x-axis in CPACS2 guide curves. We have to make a reasonable guess
        x = [1., 0., 0.]
    else:
        startScale = tigl2.fuselageGetCircumference(1, startSectionIdx, 0) / math.pi
        endScale = tigl2.fuselageGetCircumference(1, endSectionIdx - 1, 1) / math.pi
        # CAUTION There is no user-defined x-axis in CPACS2 guide curves. We have to make a reasonable guess
        x = [0., 0., 1.]

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
        print("Error during guide curve profile point calculation: The last point and the first point seem to coincide!")
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

    print("Adapting guide curve profiles to CPACS 3 definition")

    # go through all guide curve profiles
    xpath = 'cpacs/vehicles/profiles/guideCurveProfiles'

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
                print("   Removing unused guide curve profile {}".format(profileUid))
                tixi3.removeElement( xpathProfile )
                idx-=1
                nProfiles-=1
        else:
            nProfilePoints = tixi3.getVectorSize(xpathProfile + "/pointList/x")
            rX, rY, rZ = reverseEngineerGuideCurveProfilePoints(tixi2, tigl2, tigl3, guideCurveUid, nProfilePoints)

            tixi3.removeElement(xpathProfile + "/pointList")
            tixi3.createElement(xpathProfile, 'pointList')

            tixi3.addFloatVector(xpathProfile + "/pointList", 'rX', rX, len(rX), '%g')
            tixi3.addFloatVector(xpathProfile + "/pointList", 'rY', rY, len(rY), '%g')
            tixi3.addFloatVector(xpathProfile + "/pointList", 'rZ', rZ, len(rZ), '%g')


    
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
        for path in get_all_paths_matching(tixi3, xpath):
            uid = findNearestCsOrTedUid(tixi3, path)

            # get existing eta/xsi value
            value = tixi3.getDoubleElement(path)
            
            # recreate element to make sure it's empty and properly formatted
            index = elementIndexInParent(tixi3, path)
            tixi3.removeElement(path)
            tixi3.createElementAtIndex(parentPath(path), childElement(path), index)
            
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
        '//ribsPositioning/etaStart|' +
        '//ribsPositioning/etaEnd|' +
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
    for path in get_all_paths_matching(tixi3, '//ribsPositioning/elementStartUID|'):
        convertElementUidToEtaAndUid(tixi3, path, 'etaStart')
    for path in get_all_paths_matching(tixi3, '//ribsPositioning/elementEndUID|'):
        convertElementUidToEtaAndUid(tixi3, path, 'etaEnd')

def convertEtaXsiRelHeightPoints(tixi3):
    """
    Converts all spar positions to etaXsiRelHeightPoints containing eta, xsi and referenceUID
    :param tixi3: TiXI 3 handle
    """

    xpath = '//sparPosition'

    for path in get_all_paths_matching(tixi3, xpath):
        # get existing xsi value
        xsi = tixi3.getDoubleElement(path + '/xsi')
        tixi3.removeElement(path + '/xsi')
        
        if tixi3.checkElement(path + '/eta'):
            # if we have an eta, get it and find cs or ted uid
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


def get_parent_child_path(child_path):
    while child_path[-1] == '/':
        child_path = child_path[0:-1]
    pos = child_path.rindex('/')

    parent = child_path[0:pos]
    child = child_path[pos+1:]

    pos = child.rfind("[")
    if pos > 0:
        child = child[0:pos]

    return parent, child


def get_new_cs_coordinates(tigl2, tigl3, compseg_uid, eta_old, xsi_old):
    px, py, pz = tigl2.wingComponentSegmentGetPoint(compseg_uid, eta_old, xsi_old)
    return tigl3.wingComponentSegmentPointGetEtaXsi(compseg_uid, px, py, pz)


def main():
    parser = argparse.ArgumentParser(description='Converts a CPACS file from Version 2 to Version 3.')
    parser.add_argument('input_file', help='Input CPACS 2 file')
    parser.add_argument('-o', metavar='output_file', help='Name of the output file.')

    args = parser.parse_args()

    old_cpacs_file = tixiwrapper.Tixi()
    new_cpacs_file = tixi3wrapper.Tixi3()

    filename = args.input_file
    output_file = args.o

    old_cpacs_file.open(filename)
    new_cpacs_file.open(filename)
    # new_cpacs_file.usePrettyPrint(1)

    register_uids(new_cpacs_file)

    # perform structural changes
    change_cpacs_version(new_cpacs_file)
    add_missing_uids(new_cpacs_file)
    convertEtaXsiIsoLines(new_cpacs_file)
    convertEtaXsiRelHeightPoints(new_cpacs_file)
    add_changelog(new_cpacs_file)

    tigl2 = tiglwrapper.Tigl()
    tigl2.open(old_cpacs_file, "")

    tigl3 = tigl3wrapper.Tigl3()
    tigl3.open(new_cpacs_file, "")

    convertGuideCurvePoints(new_cpacs_file, old_cpacs_file, tigl2, tigl3)

    print ("Done")
    old_cpacs_file.save(filename)

    if output_file is not None:
        new_cpacs_file.save(output_file)
    else:
        print(new_cpacs_file.exportDocumentAsString())


if __name__ == "__main__":
    main()
