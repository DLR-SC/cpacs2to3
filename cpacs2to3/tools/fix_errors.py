"""
This tool tries to fix some common problems of cpacs files
such as missing uids, duplicate uids or empty elements
"""

import logging
from tixi3 import tixi3wrapper
import argparse
from cpacs2to3.cpacs_converter import fix_empty_elements, add_missing_uids, add_changelog
from cpacs2to3.uid_generator import uid_manager
import cpacs2to3.tixi_helper


def fix_wing_profiles(cpacs_file):
    """
    Reverse wing airfoils, if they are in the wrong order

    :param cpacs_file:
    """

    has_changed = False

    def get_string_vector(path):
        values = cpacs_file.getTextElement(path).split(";")
        return values

    def update_string_vector(path, values):
        cpacs_file.updateTextElement(path, ";".join(values))
        nonlocal has_changed
        has_changed = True

    paths = cpacs2to3.tixi_helper.resolve_xpaths(cpacs_file, "//wingAirfoil/pointList")

    for path in paths:
        try:
            x_points = get_string_vector(path + "/x")
            y_points = get_string_vector(path + "/y")
            z_points = get_string_vector(path + "/z")

            if len(x_points) != len(y_points) or len(x_points) != len(z_points):
                continue

            # get indices of max/min z value
            float_z = list(float(v) for v in z_points)
            max_index = float_z.index(max(float_z))
            min_index = float_z.index(min(float_z))

            if min_index > max_index:
                logging.info("Reversing wing airfoil at " + path)
                update_string_vector(path + "/x", reversed(x_points))
                update_string_vector(path + "/y", reversed(y_points))
                update_string_vector(path + "/z", reversed(z_points))

        except tixi3wrapper.Tixi3Exception:
            pass

    return has_changed


def main():
    logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG)

    parser = argparse.ArgumentParser(description='Fixed problems on a cpacs file.')
    parser.add_argument('input_file', help='Input CPACS file')
    parser.add_argument('-o', metavar='output_file', help='Name of the output file.')
    parser.add_argument('-i', help='Modify file in place, i.e. overwrite the input file.', action="store_true")

    args = parser.parse_args()

    cpacs_file = tixi3wrapper.Tixi3()

    filename = args.input_file
    output_file = args.o
    in_place = args.i

    cpacs_file.open(filename)
    cpacs_file.setCacheEnabled(1)
    cpacs_file.usePrettyPrint(1)

    uid_manager.register_all_uids(cpacs_file)

    changelog = ""

    if uid_manager.fix_invalid_uids(cpacs_file):
        changelog += "Fixed invalid uIDs. "

    if fix_empty_elements(cpacs_file):
        changelog += "Removed empty elements. "

    if add_missing_uids(cpacs_file):
        changelog += "Added missing UIDs. "

    if fix_wing_profiles(cpacs_file):
        changelog += "Fixed order of wing profiles. "

    if changelog != "":
        add_changelog(cpacs_file, changelog.strip())

    logging.info ("Done")

    if in_place:
        output_file = filename

    if output_file is not None:
        logging.info("Saving " + output_file)
        cpacs_file.save(output_file)
    else:
        logging.info(cpacs_file.exportDocumentAsString())


if __name__ == "__main__":
    main()