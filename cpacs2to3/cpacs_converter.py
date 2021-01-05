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
from cpacs2to3.convert_coordinates import convert_geometry, do_convert_guide_curves
from cpacs2to3.tixi_helper import parent_path, element_name, element_index
from cpacs2to3.uid_generator import uid_manager
from cpacs2to3.graph import Graph, CPACS2Node, CPACS3Node
from cpacs2to3.material import upgradeMaterialCpacs31


def bump_version(vers, level):
    import semver
    import re

    # allow also not semver compatible versions
    if re.match(semver._REGEX, vers):
        pass
    elif re.match("[0-9]+\.[0-9]+", vers):
        vers = vers + ".0"
    elif re.match("[0-9]+", vers):
        vers = vers + ".0.0"

    if level == "major":
        v = semver.bump_major(vers)
    elif level == "minor":
        v = semver.bump_minor(vers)
    else:
        v = semver.bump_patch(vers)
    return v

def change_cpacs_version(tixi3_handle, version_str):
    """
    Changes the CPACS Version of the file

    :param tixi3_handle: TiXI 3 handle
    """
    tixi3_handle.updateTextElement("/cpacs/header/cpacsVersion", version_str)

def get_cpacs_version(tixi3_handle):
    return tixi3_handle.getTextElement("/cpacs/header/cpacsVersion")

def add_changelog(tixi3_handle, text, creator="cpacs2to3"):
    """
    Adds a changelog entry to the cpacs file
    :param tixi3_handle: TiXI 3 handle
    :param text: text for the changelog
    """
    if not tixi3_handle.checkElement("/cpacs/header/updates"):
        tixi3_handle.createElement("/cpacs/header", "updates")

    current_version = "1.0"
    if tixi3_handle.checkElement("/cpacs/header/version"):
        current_version = tixi3_handle.getTextElement("/cpacs/header/version")
    else:
        tixi3_handle.addTextElement("/cpacs/header/version", current_version)

    next_version = bump_version(current_version, "minor")
    tixi3_handle.updateTextElement("/cpacs/header/version", next_version)

    tixi3_handle.createElement("/cpacs/header/updates", "update")
    n_updates = tixi3_handle.getNamedChildrenCount("/cpacs/header/updates", "update")
    xpath = "/cpacs/header/updates/update[%d]" % n_updates
    tixi3_handle.addTextElement(xpath, "modification", text)
    tixi3_handle.addTextElement(xpath, "creator", creator)
    tixi3_handle.addTextElement(xpath, "timestamp", datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))
    tixi3_handle.addTextElement(xpath, "version", next_version)
    cpacs_version = get_cpacs_version(tixi3_handle)
    tixi3_handle.addTextElement(xpath, "cpacsVersion", cpacs_version)


def add_uid(tixi3, xpath, uid):
    if not tixi3.checkElement(xpath):
        return False
    if not tixi3.checkAttribute(xpath, "uID"):
        tixi3.addTextAttribute(xpath, "uID", uid)
        return True
    else:
        return False


def fix_empty_elements(tixi_handle):
    """
    Some text elements may not be empty but are optional. If they are present, remove them
    """

    file_has_changed = False

    xpath = "//description|//name"
    paths = tixihelper.resolve_xpaths(tixi_handle, xpath)
    for path in paths:
        if tixi_handle.getTextElement(path) == "":
            tixi_handle.removeElement(path)
            file_has_changed = True

    return file_has_changed

def fix_guide_curve_profile_element_names(tixi_handle):
    """
    TiGL 2 uses a slight modification of the CPACS standard for guide curve profiles. If there are guide
    curves present, the elements will adapt the names expected by TiGL 2
    """

    file_has_changed = False

    if not do_convert_guide_curves(tixi_handle):
        return file_has_changed

    # rename guideCurves to guideCurveProfiles
    if tixi_handle.checkElement("cpacs/vehicles/profiles/guideCurves"):
        tixi_handle.renameElement("cpacs/vehicles/profiles", "guideCurves", "guideCurveProfiles")
        file_has_changed = True

    xpath = "cpacs/vehicles/profiles/guideCurveProfiles"
    if not tixi_handle.checkElement(xpath):
        return file_has_changed

    # rename rX to x, rY to y, rZ to z
    nProfiles = tixi_handle.getNumberOfChilds(xpath)
    idx = 0
    while idx < nProfiles:
        idx += 1
        xpathProfile = xpath + '/guideCurveProfile[{}]'.format(idx)

        if tixi_handle.checkElement(xpathProfile + "/pointList/rX"):
            tixi_handle.renameElement(xpathProfile + "/pointList", "rX", "x")
            file_has_changed = True
        if tixi_handle.checkElement(xpathProfile + "/pointList/rY"):
            tixi_handle.renameElement(xpathProfile + "/pointList", "rY", "y")
            file_has_changed = True
        if tixi_handle.checkElement(xpathProfile + "/pointList/rZ"):
            tixi_handle.renameElement(xpathProfile + "/pointList", "rZ", "z")
            file_has_changed = True

    return file_has_changed


def add_missing_uids(tixi3):

    has_changed = False

    logging.info("Add missing uIDs")
    paths = tixihelper.resolve_xpaths(tixi3, "//transformation")
    for path in paths:
        has_changed = add_uid(tixi3, path, uid_manager.create_uid(tixi3, path)) or has_changed
        has_changed = add_uid(tixi3, path + "/rotation", uid_manager.create_uid(tixi3, path + "/rotation")) or has_changed
        has_changed = add_uid(tixi3, path + "/scaling", uid_manager.create_uid(tixi3, path + "/scaling")) or has_changed
        has_changed = add_uid(tixi3, path + "/translation", uid_manager.create_uid(tixi3, path + "/translation")) or has_changed

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
        '//cargoCrossBeam/alignment|' +
        '//cargoCrossBeamStrut/alignment|' +
        '//longFloorBeamPosition|' +
        '//longFloorBeamPosition/alignment|' +
        '//trailingEdgeDevice/path/steps/step/innerHingeTranslation|' +
        '//trailingEdgeDevice/path/steps/step/outerHingeTranslation|' +
        '//trailingEdgeDevice/tracks/track|' +
        '//globalBeamProperties/beamCrossSection|' +
        '//globalBeamProperties/beamCOG|' +
        '//globalBeamProperties/beamShearCenter|' +
        '//globalBeamProperties/beamStiffness|' +
        '//sparCell|' +
        '//pressureBulkhead|' +
        '//engine/nacelle|' +
        '//paxCrossBeams/alignment' +
        '//paxCrossBeamStruts/alignment' +
        '//fuselageNodalLoad' +
        '//wingNodalLoad' +
        genMassPaths('mTOM') + '|' +
        genMassPaths('mZFM') + '|' +
        genMassPaths('mMLM') + '|' +
        genMassPaths('mMRM') + '|' +
        genMassPaths('massDescription')
    )
    try:
        paths = tixihelper.resolve_xpaths(tixi3, xpath)
        for path in paths:
            has_changed = add_uid(tixi3, path, uid_manager.create_uid(tixi3, path)) or has_changed
    except Tixi3Exception:
        pass

    return has_changed


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
            add_uid(tixi3, node_path, uid_manager.create_uid(tixi3, node_path))
            tixi3.addDoubleElement(node_path, "x", x, "%g")
            tixi3.addDoubleElement(node_path, "y", y, "%g")
            tixi3.addDoubleElement(node_path, "z", z, "%g")

        tixi3.createElement(element_path, "transformation")
        add_uid(tixi3, transformation_path, uid_manager.create_uid(tixi3, transformation_path))

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


def convert_eta_xsi_rel_height_points(tixi3):
    """
    Converts all spar positions to etaXsiRelHeightPoints containing eta, xsi and referenceUID
    :param tixi3: TiXI 3 handle
    """

    convert_spar_positions(tixi3)
    convert_ribs_positions(tixi3)
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

def rearrange_non_explicit_stringer(tixi3):
    """schema order of angle and refpoint of wingStringerType changed.

    In 3.1 angle should be after refPoint
    """
    for path in tixihelper.resolve_xpaths(tixi3, '//lowerShell/stringer|//upperShell/stringer|//cell/stringer'):
        if not tixi3.checkElement(path + '/pitch'):
            continue
        angle = tixi3.getDoubleElement(path + '/angle')
        tixi3.removeElement(path + '/angle')
        tixi3.addDoubleElement(path, 'angle', angle, None)



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


def convert_ribs_positions(tixi3):
    def replace_eta_with_curve_point(path, eta_node_name, new_node_name, reference_uid):
        if tixi3.checkElement(path + "/" + eta_node_name):
            eta_str = tixi3.getTextElement(path + '/' + eta_node_name)

            tixi3.createElement(path, new_node_name)
            tixi3.addTextElement(path + '/' + new_node_name, 'eta', eta_str)
            tixi3.addTextElement(path + '/' + new_node_name, 'referenceUID', reference_uid)

            tixi3.swapElements(path + '/' + eta_node_name, path + '/' + new_node_name)
            tixi3.removeElement(path + '/' + eta_node_name)

    for path in tixihelper.resolve_xpaths(tixi3, '//ribsPositioning'):
        rib_reference = tixi3.getTextElement(path + '/ribReference')

        replace_eta_with_curve_point(path, "etaStart", "startCurvePoint", rib_reference)
        replace_eta_with_curve_point(path, "etaEnd", "endCurvePoint", rib_reference)

        def replace_element_with_segment_coords(path, element_node_name, eta_xsi_point_name):

            if tixi3.checkElement(path + '/' + element_node_name):
                elementUID = tixi3.getTextElement(path + '/' + element_node_name)
                logging.warning("Rib '" + path + "' placed into section  element " + elementUID  + " "
                                "will be converted into eta/xsi coordinates. "
                                "In case of a rib rotation, this conversion will result in a different rib.")

                uid, eta = get_segment_etauid_from_section_element(tixi3, elementUID)

                tixi3.createElement(path, eta_xsi_point_name)
                tixi3.addTextElement(path + '/' + eta_xsi_point_name, 'eta', str(eta))
                tixi3.addTextElement(path + '/' + eta_xsi_point_name, 'referenceUID', uid)
                tixi3.addTextElement(path + '/' + eta_xsi_point_name, 'xsi', '0.0')

                tixi3.swapElements(path + '/' + element_node_name, path + '/' + eta_xsi_point_name)
                tixi3.removeElement(path + '/' + element_node_name)

        replace_element_with_segment_coords(path, 'elementStartUID', 'startEtaXsiPoint')
        replace_element_with_segment_coords(path, 'elementEndUID', 'endEtaXsiPoint')

    # explicit rib positionings
    for path in tixihelper.resolve_xpaths(tixi3, '//ribExplicitPositioning'):
        start_reference = tixi3.getTextElement(path + '/startReference')
        end_reference = tixi3.getTextElement(path + '/endReference')

        replace_eta_with_curve_point(path, "etaStart", "startCurvePoint", start_reference)
        replace_eta_with_curve_point(path, "etaEnd", "endCurvePoint", end_reference)

        # add rib start / end nodes
        tixi3.addTextElement(path, "ribStart", start_reference)
        tixi3.addTextElement(path, "ribEnd", end_reference)

        # remove the reference elements
        tixi3.removeElement(path + '/startReference')
        tixi3.removeElement(path + '/endReference')

def convert_cpacs_xml(tixi_handle):
    """
    perform structural changes on XML
    """
    # add new nodes / uids
    add_missing_uids(tixi_handle)
    add_transformation_nodes(tixi_handle)
    # convert component segment structure
    convert_eta_xsi_iso_lines(tixi_handle)
    convert_eta_xsi_rel_height_points(tixi_handle)


def upgrade_2_to_3(cpacs_handle, args):
    filename = args.input_file

    if args.fix_errors:
        file_has_changed = uid_manager.fix_invalid_uids(cpacs_handle)
        file_has_changed = fix_empty_elements(cpacs_handle) or file_has_changed
        file_has_changed = fix_guide_curve_profile_element_names(cpacs_handle) or file_has_changed

        if file_has_changed:
            logging.info("A fixed cpacs2 file will be stored to '%s'" % (filename + ".fixed"))
            with open(filename + ".fixed", "w") as text_file:
                text_file.write(cpacs_handle.exportDocumentAsString())

    # copy cpacs file into tixi 2 to make tigl2 happy
    old_cpacs_file = tixiwrapper.Tixi()
    old_cpacs_file.openString(cpacs_handle.exportDocumentAsString())

    change_cpacs_version(cpacs_handle, "3.0")
    convert_cpacs_xml(cpacs_handle)

    # perform geometric conversions using tigl
    convert_geometry(filename, cpacs_handle, old_cpacs_file)


def upgrade_3_to_31(cpacs_handle, args):
    """
    Upgrades a cpacs 3.0 dataset to 3.1
    """

    # rename relDeflection to controlParameter
    xpath = (
            '//leadingEdgeDevice/path/steps/step|' +
            '//spoiler/path/steps/step|' +
            '//trailingEdgeDevice/path/steps/step'
    )
    for path in tixihelper.resolve_xpaths(cpacs_handle, xpath):
        if cpacs_handle.checkElement(path + '/relDeflection'):
            cpacs_handle.renameElement(path, "relDeflection", "controlParameter")

    xpath = (
        '//fuselage/structure/walls/wallSegments/wallSegment'
    )

    for path in tixihelper.resolve_xpaths(cpacs_handle, xpath):
        if cpacs_handle.checkElement(path + '/negativeExtrusion'):
            cpacs_handle.renameElement(path, "negativeExtrusion", "doubleSidedExtrusion")

    rearrange_non_explicit_stringer(cpacs_handle)

    # Upgrade material definition
    upgradeMaterialCpacs31(cpacs_handle)

    change_cpacs_version(cpacs_handle, "3.1")


class VersionUpdater:
    """
    This class contains the logic to update a file to a specific cpacs version
    """

    def __init__(self):
        self.version = []
        self.update_graph = Graph()

        self.define_versions()

    def define_versions(self):
        self.version.append(CPACS2Node())
        self.version.append(CPACS3Node("3.0"))
        self.version.append(CPACS3Node("3.1"))

        self.__add_update_method("2.0", "3.0", upgrade_2_to_3)
        self.__add_update_method("3.0", "3.1", upgrade_3_to_31)

    def __add_update_method(self, vold_str, vnew_str, updater):
        old_version_node = self.__get_version_node(vold_str)
        new_version_node = self.__get_version_node(vnew_str)

        self.update_graph.add_edge(old_version_node, new_version_node, update=updater)

    def __get_version_node(self, version_str):
        for v in self.version:
            if v.matches(version_str):
                return v

        return None

    def update(self, cpacs, args, target_version):
        """
        Updates the given cpacs file to given version

        :param cpacs: cpacs file handle
        :param args: command line args
        :param target_version: target version to convert to
        """

        current_version = get_cpacs_version(cpacs)

        version_old = self.__get_version_node(current_version)
        version_new = self.__get_version_node(target_version)

        if version_old is None:
            raise RuntimeError("Cannot upgrade from version " + current_version)

        if version_new is None or target_version != version_new.major_version:
            raise RuntimeError("Cannot upgrade to version " + target_version)

        path = self.update_graph.find_path(version_old, version_new)

        if path is None:
            raise RuntimeError("Don't know how to upgrade from %s to %s" % (current_version, target_version))

        if len(path) == 1:
            print("%s is compatible to %s. No actions required... " % (current_version, target_version))
            return

        logging.info("Upgrading CPACS %s file to CPACS version %s" % (current_version, target_version))

        for i in range(len(path) - 1):
            updater = self.update_graph.get_edge(path[i], path[i + 1])
            updater.update(cpacs, args)


def main():
    logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG)

    parser = argparse.ArgumentParser(description='Converts a CPACS file from Version 2 to Version 3.')
    parser.add_argument('input_file', help='Input CPACS 2 file')
    parser.add_argument('-o', metavar='output_file', help='Name of the output file.')
    parser.add_argument('--fix-errors', '-f', help='try to fix empty and duplicate uids/elements',  action="store_true")
    parser.add_argument('--target-version', '-v', default="3.1")

    args = parser.parse_args()
    filename = args.input_file

    cpacs_file = tixi3wrapper.Tixi3()
    cpacs_file.open(filename)
    cpacs_file.setCacheEnabled(1)
    cpacs_file.usePrettyPrint(1)

    # get all uids
    uid_manager.register_all_uids(cpacs_file)

    version_new = args.target_version

    vu = VersionUpdater()
    vu.update(cpacs_file, args, version_new)

    add_changelog(cpacs_file, "Converted to CPACS %s using cpacs2to3" % version_new)

    logging.info("Done")

    output_file = args.o
    if output_file is not None:
        logging.info("Saving file to '" + output_file + "'")
        cpacs_file.save(output_file)
    else:
        logging.info(cpacs_file.exportDocumentAsString())


if __name__ == "__main__":
    main()
