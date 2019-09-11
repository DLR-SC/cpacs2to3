import logging
import math

import numpy as np
import tigl3.configuration
from OCC.TopoDS import topods
from tigl import tiglwrapper
from tigl3 import tigl3wrapper
from tigl3.configuration import transform_wing_profile_geometry
from tigl3.geometry import get_length

from cpacs2to3 import tixi_helper as tixihelper
from cpacs2to3.tixi_helper import parent_path


def get_new_cs_coordinates(tigl2, tigl3, compseg_uid, eta_old, xsi_old):
    """
    Computes cpacs-3 eta/xsi coordinates of the component segment system based on the cpacs-2 values
    :return:
    """

    px, py, pz = tigl2.wingComponentSegmentGetPoint(compseg_uid, eta_old, xsi_old)
    return tigl3.wingComponentSegmentPointGetEtaXsi(compseg_uid, px, py, pz)


def convert_eta_xsi_values(tixi3, tigl2, tigl3):
    """
    Converts all eta and xsi coordinates from the old component segment eta/xsi space to the new one
    :param tixi3: TiXI 3 handle
    :param tigl2: TiGL 2 handle
    :param tigl3: TiGL 3 handle
    """

    csUids = [tixi3.getTextAttribute(xpath, 'uID') for xpath in tixihelper.resolve_xpaths(tixi3, '//componentSegment[@uID]')]
    wingSegmentUids = [tixi3.getTextAttribute(xpath, 'uID') for xpath in
                       tixihelper.resolve_xpaths(tixi3, '//wing/segments/segment[@uID]')]
    tedUids = [tixi3.getTextAttribute(xpath, 'uID') for xpath in
               tixihelper.resolve_xpaths(tixi3, '//trailingEdgeDevice[@uID]')]

    etaXpath = (
        '//track/eta|' +
        '//cutOutProfile/eta|' +
        '//intermediateAirfoil/eta|'
        # to convert eta/xsi values for wing cells, we have to convert them pairwise (eta and xsi together)
        # but the cell borders might be described by spars and ribs, so we would have to interpret the borders on a spar or rib
        # this is hard, so we skip this for now
        #        '//positioningInnerBorder/eta1|' +
        #        '//positioningOuterBorder/eta1|' +
        #        '//positioningInnerBorder/eta2|' +
        #        '//positioningOuterBorder/eta2|' +
        # rib eta values depend on the reference line specified in ribReference or startReference/endReference
        # those do not need to be converted
        #        '//ribsPositioning/etaStart|' +
        #        '//ribsPositioning/etaEnd|' +
        #        '//ribExplicitPositioning/etaStart|' +
        #        '//ribExplicitPositioning/etaEnd|' +
        # similar problem as with wing cells
        #        '//innerBorder/etaLE|' +
        #        '//outerBorder/etaLE|' +
        #        '//innerBorder/etaTE|' +
        #        '//outerBorder/etaTE|' +
        # we believe this is coupled with the xsiInside parameter
        #        '//position/etaOutside|' +
        # we do not have to convert these, as these are eta values on the spar (TODO: confirm this)
        #        '//sparCell/fromEta|' +
        #        '//sparCell/toEta'
    )

    # read all eta/uid definitions
    for xpath in tixihelper.resolve_xpaths(tixi3, etaXpath):
        eta = tixi3.getDoubleElement(xpath + '/eta')
        uid = tixi3.getTextElement(xpath + '/referenceUID')

        # TODO: determine xsi for all possible elements in etaXpath
        # e.g. ribsPositioning/ribReference: leadingEdge = 0, trailingEdge = 1
        xsi = 0

        if uid in csUids:
            newEta = get_new_cs_coordinates(tigl2, tigl3, uid, eta, xsi)[0]
            tixi3.updateDoubleElement(xpath + '/eta', newEta, '%g')
        elif uid in wingSegmentUids:
            # eta and xsi values in wing segments (which originated from wing sections) stay the same
            pass
        elif uid in tedUids:
            # TODO has this even changed?
            pass
        else:
            print(
                'ERROR: uid ' + uid + ' could not be resolved to a component segment, wing segment or trailing edge device')

    xsiXpath = (''
                #        '//stringer/innerBorderXsiLE|' +
                #        '//stringer/innerBorderXsiTE|' +
                #        '//stringer/outerBorderXsiLE|' +
                #        '//stringer/outerBorderXsiTE|' +
                #        '//innerBorder/xsiLE|' +
                #        '//outerBorder/xsiLE|' +
                #        '//innerBorder/xsiTE|' +
                #        '//outerBorder/xsiTE|' +
                #        '//position/xsiInside'
                )

    # read all xsi/uid definitions
    for xpath in tixihelper.resolve_xpaths(tixi3, xsiXpath):
        xsi = tixi3.getDoubleElement(xpath + '/xsi')
        uid = tixi3.getTextElement(xpath + '/referenceUID')

        # TODO: determine eta for all possible elements in etaXpath
        # e.g. for wing cells we have to resolve inner and outer border, and if they point to ribs, we have to compute eta values for the ribs ...
        eta = 0

        if uid in csUids:
            newXsi = get_new_cs_coordinates(tigl2, tigl3, uid, eta, xsi)[1]
            tixi3.updateDoubleElement(xpath + '/xsi', newXsi, '%g')
        elif uid in wingSegmentUids:
            # eta and xsi values in wing segments (which originated from wing sections) stay the same
            pass
        elif uid in tedUids:
            # TODO has this even changed?
            pass
        else:
            print(
                'ERROR: uid ' + uid + ' could not be resolved to a component segment, wing segment or trailing edge device')

    # read all eta/xsi pairs
    for xpath in tixihelper.resolve_xpaths(tixi3, '//sparPosition/sparPositionEtaXsi|//stringer/refPoint'):
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
            print(
                'ERROR: uid ' + uid + ' could not be resolved to a component segment, wing segment or trailing edge device')

    # reopen as we changed the TiXI document underneath
    # otherwise the changes to the TiXI document will be overwritten when TiGL saves the document
    logging.info("Reloading CPACS-3 file with TiGL 3")
    tigl3.open(tixi3, '')


def get_chord_scale(wing, wing_connection):
    """
    Returns the chord scale of the given wing connection
    :param wing:
    :param wing_connection:
    :return:
    """

    wing_transform = wing.get_transformation_matrix()
    inner_profile_wire = wing_connection.get_profile().get_chord_line_wire()
    inner_chord_line_wire = transform_wing_profile_geometry(wing_transform, wing_connection, inner_profile_wire)
    return get_length(topods.Wire(inner_chord_line_wire))


def get_inner_and_outer_scale(tigl3_h, wingUid, segmentUid):
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

    inner_connection = segment.get_inner_connection()
    outer_connection = segment.get_outer_connection()
    return get_chord_scale(wing, inner_connection), get_chord_scale(wing, outer_connection)


def find_guide_curve_using_profile(tixi2, profileUid):
    # check all guide curves of all fuselages and wings
    for type in ['fuselage', 'wing']:
        xpath = 'cpacs/vehicles/aircraft/model/{}s'.format(type)
        if not tixi2.checkElement(xpath):
            continue
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


def compute_new_guide_curve_points(tixi2, tigl2, tigl3, guide_curve_uid, n_profile_points):
    guideCurveXPath = tixi2.uIDGetXPath(guide_curve_uid)

    # get start segment and end segment to determine the scale
    segmentXPath = parent_path(parent_path(guideCurveXPath))

    rX = np.zeros([n_profile_points + 2, 1])
    rY = np.zeros([n_profile_points + 2, 1])
    rZ = np.zeros([n_profile_points + 2, 1])

    # check if the guideCurve is on a wing or a fuselage
    if 'wing' in guideCurveXPath:
        wingXPath = parent_path(parent_path(segmentXPath))
        wingUid = tixi2.getTextAttribute(wingXPath, 'uID')
        segmentUid = tixi2.getTextAttribute(segmentXPath, 'uID')

        startScale, endScale = get_inner_and_outer_scale(tigl3, wingUid, segmentUid)

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

    try:
        px, py, pz = tigl2.getGuideCurvePoints(guide_curve_uid, n_profile_points + 2)
    except:
        logging.error("Cannot parse CPACS 2 Guide Curves using TiGL. Try running cpacs2to3 with -f option.")
        quit()
        return None

    guideCurvePnts = np.zeros((3, n_profile_points + 2))
    guideCurvePnts[0, :] = px
    guideCurvePnts[1, :] = py
    guideCurvePnts[2, :] = pz

    start = guideCurvePnts[:, 0]
    end = guideCurvePnts[:, -1]

    z = np.cross(x, end - start)

    znorm = np.linalg.norm(z)
    if abs(znorm) < 1e-10:
        logging.error(
            "Error during guide curve profile point calculation: The last point and the first point seem to coincide!")
        return None

    z = z / znorm

    for i in range(0, np.size(guideCurvePnts, 1)):
        current = guideCurvePnts[:, i]

        # orthogonal projection
        ny2 = np.dot(end - start, end - start)
        rY[i] = np.dot(current - start, end - start) / ny2

        scale = (1 - rY[i]) * startScale + rY[i] * endScale
        midPoint = (1 - rY[i]) * start + rY[i] * end

        rX[i] = np.dot(current - midPoint, x) / scale
        rZ[i] = np.dot(current - midPoint, z) / scale

    # post-processing. Remove first and last point
    rX = rX[1:-1]
    rY = rY[1:-1]
    rZ = rZ[1:-1]

    return rX, rY, rZ


def convert_guide_curve_points(tixi3, tixi2, tigl2, tigl3, keep_unused_profiles=False):

    # rename guideCurveProfiles to guideCurves
    if tixi3.checkElement("cpacs/vehicles/profiles/guideCurveProfiles"):
        tixi3.renameElement("cpacs/vehicles/profiles", "guideCurveProfiles", "guideCurves")

    xpath = "cpacs/vehicles/profiles/guideCurves"
    if not tixi3.checkElement(xpath):
        return

    logging.info("Adapting guide curve profiles to CPACS 3 definition")

    nProfiles = tixi3.getNumberOfChilds(xpath)
    idx = 0
    while idx < nProfiles:
        idx += 1
        xpathProfile = xpath + '/guideCurveProfile[{}]'.format(idx)
        profileUid = tixi3.getTextAttribute(xpathProfile, 'uID')

        guideCurveUid = find_guide_curve_using_profile(tixi3, profileUid)

        if guideCurveUid is None:
            # The guide curve profile appears to be unused
            if not keep_unused_profiles:
                # If we don't need it, let's do some clean up
                logging.info("   Removing unused guide curve profile {}".format(profileUid))
                tixi3.removeElement(xpathProfile)
                idx -= 1
                nProfiles -= 1
        else:
            # rename x to rX
            if tixi3.checkElement(xpathProfile + "/pointList/x"):
                tixi3.renameElement(xpathProfile + "/pointList", "x", "rX")
            nProfilePoints = tixi3.getVectorSize(xpathProfile + "/pointList/rX")

            rX, rY, rZ = compute_new_guide_curve_points(tixi2, tigl2, tigl3, guideCurveUid, nProfilePoints)

            tixi3.removeElement(xpathProfile + "/pointList")
            tixi3.createElement(xpathProfile, "pointList")
            tixi3.addFloatVector(xpathProfile + "/pointList", "rX", rX, len(rX), "%g")
            tixi3.addFloatVector(xpathProfile + "/pointList", "rY", rY, len(rY), "%g")
            tixi3.addFloatVector(xpathProfile + "/pointList", "rZ", rZ, len(rZ), "%g")


def convert_geometry(filename, new_cpacs_file, old_cpacs_file):
    """
    Geometric conversion main routine
    :return:
    """

    tigl2 = tiglwrapper.Tigl()
    logging.info("Loading CPACS-2 file '" + filename + "' with TiGL 2")
    tigl2.open(old_cpacs_file, "")
    logging.info("Loading CPACS-3 file with TiGL 3")
    tigl3 = tigl3wrapper.Tigl3()
    tigl3.open(new_cpacs_file, "")

    convert_guide_curve_points(new_cpacs_file, old_cpacs_file, tigl2, tigl3)
    convert_eta_xsi_values(new_cpacs_file, tigl2, tigl3)
