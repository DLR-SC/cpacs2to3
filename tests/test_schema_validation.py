from cpacs2to3.cpacs_converter import upgrade_2_to_3, upgrade_3_to_31

def test_valid_schema(simple_test):
    "test, if output is cpacs 3 schema conform"

    upgrade_2_to_3(simple_test.new_cpacs_file, simple_test)

    simple_test.old_cpacs_file.schemaValidateFromFile("tests/TestData/cpacs_2.3.1.xsd")
    simple_test.new_cpacs_file.schemaValidateFromFile("tests/TestData/cpacs_3.0.0.xsd")

    upgrade_3_to_31(simple_test.new_cpacs_file, simple_test)

    simple_test.new_cpacs_file.schemaValidateFromFile("tests/TestData/cpacs_3.1.0.xsd")
