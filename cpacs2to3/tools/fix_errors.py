"""
This tool tries to fix some common problems of cpacs files
such as missing uids, duplicate uids or empty elements
"""

import logging
from tixi3 import tixi3wrapper
import argparse
from cpacs2to3.cpacs_converter import fix_empty_elements, add_missing_uids, add_changelog
from cpacs2to3.uid_generator import uid_manager


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
    uid_manager.fix_invalid_uids(cpacs_file)

    fix_empty_elements(cpacs_file)
    add_missing_uids(cpacs_file)

    add_changelog(cpacs_file, "Fixed cpacs errors")

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