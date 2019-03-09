"""
This tool converts CPACS file from Version 2 to 3.

Currently is does:
 - Adds missing uiDs
 - Changes the version number
 - Geometry of wing structure
 - Converts guide curves
"""

import argparse
import logging
import re
from datetime import datetime

from tixi import tixiwrapper
from tixi3 import tixi3wrapper
from tixi3.tixi3wrapper import Tixi3Exception

import cpacs2to3.tixi_helper as tixihelper
from cpacs2to3.convert_coordinates import convert_geometry
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


def fix_empty_elements(tixi_handle):
    """
    Some text elements may not be empty but are optional. If they are present, remove them
    """

    xpath = "//description|//name"
    paths = tixihelper.resolve_xpaths(tixi_handle, xpath)
    for path in paths:
        if tixi_handle.getTextElement(path) == "":
            tixi_handle.removeElement(path)


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


def get_parent_compseg_or_ted_uid(tixi3, xpath):
    """
    Finds the uid of the nearest parent which is a component segment or trailing edge device
    :param tixi3: TiXI 3 handle
    :param xpath: XPath of the element to start the search
    """
    end = [it.end() for it in re.finditer('(componentSegment|trailingEdgeDevice)(\[\d+\])?/', xpath)][-1]
    csOrTedXPath = xpath[:end - 1]
    uid = tixi3.getTextAttribute(csOrTedXPath, 'uID')
    return uid


def get_segment_etauid_from_section_element(tixi3, elementUid):
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

    return uid, eta


def convert_element_uid_to_eta_and_uid(tixi3, xpath, elementName, xsi):
    """
    Converts an elementUID element to an eta/xsi value and a referenceUID to a wing segment referencing the wing section element from elementUID.
    Removes the elementUID element and adds eta and referenceUID elements with new values
    :param tixi3: TiXI 3 handle
    :param xpath: The xpath of the elementUID element
    :param elementName: Name of the element created at xpath which contains the computed eta and referenceUID elements
    :param xsi: xsi
    """

    # read and remove elementUid
    elementUid = tixi3.getTextElement(xpath)
    index = element_index(tixi3, xpath)
    tixi3.removeElement(xpath)
    
    uid, eta = get_segment_etauid_from_section_element(tixi3, elementUid)
    
    # write eta iso line
    parentXPath = parent_path(xpath)
    tixi3.createElementAtIndex(parentXPath, elementName, index)
    newElementXPath = parentXPath + '/' + elementName
    tixi3.addDoubleElement(newElementXPath, 'eta', eta, '%g')
    tixi3.addDoubleElement(newElementXPath, 'xsi', xsi, '%g')
    tixi3.addTextElement(newElementXPath, 'referenceUID', uid)


def convert_eta_xsi_iso_lines(tixi3):
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
            uid = get_parent_compseg_or_ted_uid(tixi3, path)

            # get existing eta/xsi value
            value_str = tixi3.getTextElement(path)
            try:
                value = float(value_str)

                # recreate element to make sure it's empty and properly formatted
                index = element_index(tixi3, path)
                tixi3.removeElement(path)
                tixi3.createElementAtIndex(parent_path(path), element_name(path), index)

                # add sub elements for eta/xsi iso line
                tixi3.addDoubleElement(path, elementName, value, '%g')
                tixi3.addTextElement(path, 'referenceUID', uid)
            except ValueError:
                # don't convert values that are already converted
                pass

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
    #for path in tixihelper.resolve_xpaths(tixi3, '//ribsPositioning/elementStartUID|'):
    #    convertElementUidToEtaAndUid(tixi3, path, 'etaStart')
    #for path in tixihelper.resolve_xpaths(tixi3, '//ribsPositioning/elementEndUID|'):
    #    convertElementUidToEtaAndUid(tixi3, path, 'etaEnd')


def convert_eta_xsi_rel_height_points(tixi3):
    """
    Converts all spar positions to etaXsiRelHeightPoints containing eta, xsi and referenceUID
    :param tixi3: TiXI 3 handle
    """

    convert_spar_positions(tixi3)
    convert_non_explicit_stringer(tixi3)


def convert_non_explicit_stringer(tixi3):
    # convert non-explicit stringer
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

        uid = get_parent_compseg_or_ted_uid(tixi3, path)

        # add sub elements for rel height point
        tixi3.createElement(path, 'refPoint')
        path = path + '/refPoint'
        tixi3.addDoubleElement(path, 'eta', eta, '%g')
        tixi3.addDoubleElement(path, 'xsi', xsi, '%g')
        tixi3.addTextElement(path, 'referenceUID', uid)


def convert_spar_positions(tixi3):

    # convert sparPosition
    for path in tixihelper.resolve_xpaths(tixi3, '//sparPosition'):
        # get existing xsi value
        xsi = tixi3.getDoubleElement(path + '/xsi')
        tixi3.removeElement(path + '/xsi')

        if tixi3.checkElement(path + '/eta'):
            # if we have an eta, get it
            eta = tixi3.getDoubleElement(path + '/eta')
            tixi3.removeElement(path + '/eta')

            uid = get_parent_compseg_or_ted_uid(tixi3, path)

            # add sub elements for rel height point
            tixi3.createElement(path, 'sparPositionEtaXsi')
            path = path + '/sparPositionEtaXsi'
            tixi3.addDoubleElement(path, 'eta', eta, '%g')
            tixi3.addDoubleElement(path, 'xsi', xsi, '%g')
            tixi3.addTextElement(path, 'referenceUID', uid)
        elif tixi3.checkElement(path + "/elementUID"):
            # in case of elementUID, find wing segment which references the element and convert to eta
            convert_element_uid_to_eta_and_uid(tixi3, path + '/elementUID', "sparPositionEtaXsi", xsi)


def convert_cpacs_xml(tixi_handle):
    """
    perform structural changes on XML
    """
    change_cpacs_version(tixi_handle)
    add_changelog(tixi_handle)
    # add new nodes / uids
    add_missing_uids(tixi_handle)
    add_transformation_nodes(tixi_handle)
    # convert component segment structure
    convert_eta_xsi_iso_lines(tixi_handle)
    convert_eta_xsi_rel_height_points(tixi_handle)




def main():
    logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG)

    parser = argparse.ArgumentParser(description='Converts a CPACS file from Version 2 to Version 3.')
    parser.add_argument('input_file', help='Input CPACS 2 file')
    parser.add_argument('-o', metavar='output_file', help='Name of the output file.')
    parser.add_argument('--fix-errors', '-f', help='try to fix empty and duplicate uids/elements',  action="store_true")

    args = parser.parse_args()
    do_fix_uids = args.fix_errors

    old_cpacs_file = tixiwrapper.Tixi()
    new_cpacs_file = tixi3wrapper.Tixi3()

    filename = args.input_file
    output_file = args.o

    new_cpacs_file.open(filename)
    new_cpacs_file.setCacheEnabled(1)

    # get all uids
    invalid_uids, empty_uids = register_uids(new_cpacs_file)
    if do_fix_uids:
        if len(invalid_uids) + len(empty_uids) > 0:
            tixihelper.fix_invalid_uids(empty_uids, invalid_uids, new_cpacs_file)

        fix_empty_elements(new_cpacs_file)

        logging.info("A fixed cpacs2 file will be stored to '%s'" % (filename + ".fixed"))
        with open(filename + ".fixed", "w") as text_file:
            text_file.write(new_cpacs_file.exportDocumentAsString())

    old_cpacs_file.openString(new_cpacs_file.exportDocumentAsString())

    convert_cpacs_xml(new_cpacs_file)

    # perform geometric conversions using tigl
    convert_geometry(filename, new_cpacs_file, old_cpacs_file)

    logging.info ("Done")

    if output_file is not None:
        logging.info("Saving file to '" + output_file + "'")
        new_cpacs_file.save(output_file)
    else:
        logging.info(new_cpacs_file.exportDocumentAsString())



if __name__ == "__main__":
    main()
