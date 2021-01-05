import pytest
from cpacs2to3.uid_generator import uid_manager
from cpacs2to3.cpacs_converter import fix_empty_elements
from tixi import tixiwrapper
from tixi3 import tixi3wrapper

class TestCase:
    input_file = None
    old_cpacs_file = None
    new_cpacs_file = None
    fix_errors = False

    def __init__(self, file, old, new):
        self.input_file = file
        self.old_cpacs_file = old
        self.new_cpacs_file = new


@pytest.fixture
def simple_test():

    file_name = "tests/TestData/simpletest.cpacs.xml"

    old_cpacs_file = tixiwrapper.Tixi()
    new_cpacs_file = tixi3wrapper.Tixi3()

    new_cpacs_file.open(file_name)
    new_cpacs_file.setCacheEnabled(1)
    new_cpacs_file.usePrettyPrint(1)

    uid_manager.register_all_uids(new_cpacs_file)
    uid_manager.fix_invalid_uids(new_cpacs_file)
    fix_empty_elements(new_cpacs_file)

    old_cpacs_file.openString(new_cpacs_file.exportDocumentAsString())

    return TestCase(file_name, old_cpacs_file, new_cpacs_file)
