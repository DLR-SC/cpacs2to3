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
            if parent == '':
                break;

        if parent != '':
            parent_uid = tixi_handle.getTextAttribute(parent, "uID")
        else:
            parent_uid = ''

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

    convertIsoLineCoords(tixi3, etaXpath, 'eta')
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

    # convert sparPosition
    for path in get_all_paths_matching(tixi3, '//sparPosition'):
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

    # convert non-explicit stringer
    for path in get_all_paths_matching(tixi3, '//lowerShell/stringer|//upperShell/stringer|//cell/stringer'):
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

def convertCSEtaCoord(tigl2, tigl3, compseg_uid, eta_old):
    return get_new_cs_coordinates(tigl2, tigl3, compseg_uid, eta_old, 0.0)[0]
    
def convertCSXsiCoord(tigl2, tigl3, compseg_uid, xsi_old):
    return get_new_cs_coordinates(tigl2, tigl3, compseg_uid, 0.0, xsi_old)[1]
    
def convertEtaXsiValues(tixi3, tigl2, tigl3):
    """
    Converts all eta and xsi coordinates from the old component segment eta/xsi space to the new one
    :param tixi3: TiXI 3 handle
    :param tigl2: TiGL 2 handle
    :param tigl3: TiGL 3 handle
    """
    
    csUids          = [tixi3.getTextAttribute(xpath, 'uID') for xpath in get_all_paths_matching(tixi3, '//componentSegment')]
    wingSegmentUids = [tixi3.getTextAttribute(xpath, 'uID') for xpath in get_all_paths_matching(tixi3, '//wing/segments/segment')]
    tedUids         = [tixi3.getTextAttribute(xpath, 'uID') for xpath in get_all_paths_matching(tixi3, '//trailingEdgeDevice')]

    # read all eta definitions
    for xpath in get_all_paths_matching(tixi3, etaXpath):
        eta = tixi3.getDoubleElement(xpath + '/eta')
        uid = tixi3.getTextElement(xpath + '/referenceUID')

        if uid in csUids:
            newEta = convertCSEtaCoord(tigl2, tigl3, uid, eta)
            tixi3.updateDoubleElement(xpath + '/eta', newEta, '%g')
        elif uid in wingSegmentUids:
            # eta and xsi values in wing segments (which originated from wing sections) stay the same
            pass
        elif uid in tedUids:
            # TODO has this even changed?
            pass
        else:
            print('ERROR: uid ' + uid + ' could not be resolved to a component segment, wing segment or trailing edge device')
            
    # read all xsi definitions
    for xpath in get_all_paths_matching(tixi3, xsiXpath):
        xsi = tixi3.getDoubleElement(xpath + '/xsi')
        uid = tixi3.getTextElement(xpath + '/referenceUID')

        if uid in csUids:
            newXsi = convertCSXsiCoord(tigl2, tigl3, uid, xsi)
            tixi3.updateDoubleElement(xpath + '/xsi', newXsi, '%g')
        elif uid in wingSegmentUids:
            # eta and xsi values in wing segments (which originated from wing sections) stay the same
            pass
        elif uid in tedUids:
            # TODO has this even changed?
            pass
        else:
            print('ERROR: uid ' + uid + ' could not be resolved to a component segment, wing segment or trailing edge device')

    # read all etaXsiRelHeightPoints
    for xpath in get_all_paths_matching(tixi3, '//sparPosition/sparPoint|//stringer/refPoint'):
        xsi = tixi3.getDoubleElement(xpath + '/xsi')
        eta = tixi3.getDoubleElement(xpath + '/eta')
        uid = tixi3.getTextElement(xpath + '/referenceUID')

        if uid in csUids:
            newEtaXsi = get_new_cs_coordinates(tigl2, tigl3, uid, eta, xsi)
            tixi3.updateDoubleElement(xpath + '/eta', newEtaXsi[0], '%g')
            tixi3.updateDoubleElement(xpath + '/xsi', newEtaXsi[1], '%g')
        elif uid in wingSegmentUids:
            # eta and xsi values in wing segments (which originated from wing sections) stay the same
            pass
        elif uid in tedUids:
            # TODO has this even changed?
            pass
        else:
            print('ERROR: uid ' + uid + ' could not be resolved to a component segment, wing segment or trailing edge device')
            
    # reopen as we changed the TiXI document underneath
    # otherwise the changes to the TiXI document will be overwritten when TiGL saves the document
    tigl3.open(tixi3, '')

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

    # perform structural changes on XML
    change_cpacs_version(new_cpacs_file)
    add_missing_uids(new_cpacs_file)
    convertEtaXsiIsoLines(new_cpacs_file)
    convertEtaXsiRelHeightPoints(new_cpacs_file)
    add_changelog(new_cpacs_file)

    # load old and new XML into TiGL
    tigl2 = tiglwrapper.Tigl()
    tigl2.open(old_cpacs_file, "")

    tigl3 = tigl3wrapper.Tigl3()
    tigl3.open(new_cpacs_file, "")

    # perform non-structural conversions
    convertEtaXsiValues(new_cpacs_file, tigl2, tigl3)
    
    print ("Done")
    old_cpacs_file.save(filename)

    if output_file is not None:
        new_cpacs_file.save(output_file)
    else:
        print(new_cpacs_file.exportDocumentAsString())


if __name__ == "__main__":
    main()
