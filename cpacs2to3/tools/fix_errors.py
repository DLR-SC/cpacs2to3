"""
This tool tries to fix some common problems of cpacs files
such as missing uids, duplicate uids or empty elements
"""

import logging
from tixi3 import tixi3wrapper
import cpacs2to3.tixi_helper as tixihelper
import argparse
from cpacs2to3.cpacs_converter import fix_empty_elements, register_uids, add_missing_uids


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

    invalid_uids, empty_uids = register_uids(cpacs_file)

    tixihelper.fix_invalid_uids(empty_uids, invalid_uids, cpacs_file)
    fix_empty_elements(cpacs_file)
    add_missing_uids(cpacs_file)

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