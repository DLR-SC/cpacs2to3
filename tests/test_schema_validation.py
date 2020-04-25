from cpacs2to3.cpacs_converter import convert_cpacs_xml, convert_geometry, change_cpacs_version
from tixi3.tixi3wrapper import ReturnCode

def test_valid_schema(simple_test):
    "test, if output is cpacs 3 schema conform"

    change_cpacs_version(simple_test.new_cpacs_file, "3.0")
    convert_cpacs_xml(simple_test.new_cpacs_file)
    convert_geometry(simple_test.input_file,
                     simple_test.new_cpacs_file,
                     simple_test.old_cpacs_file)

    simple_test.old_cpacs_file.schemaValidateFromFile("tests/TestData/cpacs_2.3.1.xsd")
    simple_test.new_cpacs_file.schemaValidateFromFile("tests/TestData/cpacs_3.0.0.xsd")
