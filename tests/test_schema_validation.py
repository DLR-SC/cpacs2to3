from cpacs2to3.cpacs_converter import convert_cpacs_xml, convert_geometry
from tixi3.tixi3wrapper import ReturnCode

def test_valid_schema(simple_test):
    "test, if output is cpacs 3 schema conform"

    convert_cpacs_xml(simple_test.new_cpacs_file)
    convert_geometry(simple_test.input_file,
                     simple_test.new_cpacs_file,
                     simple_test.old_cpacs_file)

    # from tixi3.tixi3wrapper import Tixi3
    # simple_test.new_cpacs_file = Tixi3()
    # simple_test.new_cpacs_file.open("tests/TestData/simpletest.cpacs.tigl3.xml")

    schema = "tests/TestData/cpacs_3.0.0_schema.xsd"
    assert(ReturnCode.SUCCESS == simple_test.new_cpacs_file.schemaValidateFromFile(schema))
