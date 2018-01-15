from __future__ import print_function

from tigl import tiglwrapper
from tigl3 import tigl3wrapper

from tixi3 import tixi3wrapper
from tixi3.tixi3wrapper import Tixi3Exception
from tixi import tixiwrapper

from datetime import datetime


class UIDGenerator(object):
    def __init__(self):
        self.counter = 0
        self.uids = set()

    def create(self, tixi_handle, current_path):
        parent, elem = get_parent_child_path(current_path)
        while not tixi_handle.checkAttribute(parent, "uID"):
            parent, _ = get_parent_child_path(parent)

        parent_uid = tixi_handle.getTextAttribute(parent, "uID")

        counter = 1
        new_uid = "%s_%s%d" % (parent_uid, elem, counter)
        while self.uid_exists(new_uid):
            counter += 1
            new_uid = "%s_%s%d" % (parent_uid, elem, counter)

        self.register(new_uid)
        return new_uid

    def register(self, uid):
        """
        Register an existing uid at the generator
        This is, to make sure this uid won't generated
        to avoid duplication of UIDs.
        :param uid:
        """
        self.uids.add(uid)

    def uid_exists(self, uid):
        return uid in self.uids


uidGenerator = UIDGenerator()


def register_uids(tixi3_handle):
    """
    Gets all elements with uiDs and registers them
    :param tixi3_handle:
    """
    print ("Registering all uIDs")
    paths = get_all_paths_matching(tixi3_handle, "//*[@uID]")
    for elem in paths:
        uid = tixi3_handle.getTextAttribute(elem, "uID")
        uidGenerator.register(uid)


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


def get_all_paths_matching(tixi3, xpath):
    try:
        n_nodes = tixi3.xPathEvaluateNodeNumber(xpath)
        paths = []
        for i in range(0, n_nodes):
            paths.append(tixi3.xPathExpressionGetXPath(xpath, i+1))
        return paths
    except Tixi3Exception:
        return []


def add_uid(tixi3, xpath, uid):
    if not tixi3.checkElement(xpath):
        return
    if not tixi3.checkAttribute(xpath, "uID"):
        tixi3.addTextAttribute(xpath, "uID", uid)


def add_missing_uids(tixi3):
    print("Add missing uIDs")
    paths = get_all_paths_matching(tixi3, "//transformation")
    for path in paths:
        add_uid(tixi3, path, uidGenerator.create(tixi3, path))
        add_uid(tixi3, path + "/rotation", uidGenerator.create(tixi3, path + "/rotation"))
        add_uid(tixi3, path + "/scaling", uidGenerator.create(tixi3, path + "/scaling"))
        add_uid(tixi3, path + "/translation", uidGenerator.create(tixi3, path + "/translation"))

    # add uids to positinings, lowerShells, upperShells, rotorBladeAttachments
    xpath = '//positioning|//lowerShell|//upperShell|//rotorBladeAttachment|//ribRotation'
    try:
        paths = get_all_paths_matching(tixi3, xpath)
        for path in paths:
            add_uid(tixi3, path, uidGenerator.create(tixi3, path))
    except Tixi3Exception:
        pass


def get_parent_child_path(child_path):
    while child_path[-1] == '/':
        child_path = child_path[0:-1]
    pos = child_path.rindex('/')

    parent = child_path[0:pos]
    child = child_path[pos+1:]

    pos = child.rfind("[")
    if pos > 0:
        child = child[0:pos]

    return parent, child


def get_new_cs_coordinates(tigl2, tigl3, compseg_uid, eta_old, xsi_old):
    px, py, pz = tigl2.wingComponentSegmentGetPoint(compseg_uid, eta_old, xsi_old)
    return tigl3.wingComponentSegmentPointGetEtaXsi(compseg_uid, px, py, pz)


old_cpacs_file = tixiwrapper.Tixi()
new_cpacs_file = tixi3wrapper.Tixi3()

filename = "simpletest-nacelle-mod.xml"
output_file = "simpletest-nacelle-mod_old.cpacs.xml"

old_cpacs_file.open(filename)
new_cpacs_file.open(filename)
# new_cpacs_file.usePrettyPrint(1)

register_uids(new_cpacs_file)

# perform structural changes
change_cpacs_version(new_cpacs_file)
add_missing_uids(new_cpacs_file)
add_changelog(new_cpacs_file)

tigl2 = tiglwrapper.Tigl()
tigl2.open(old_cpacs_file, "")

tigl3 = tigl3wrapper.Tigl3()
tigl3.open(new_cpacs_file, "")

print ("Done")
old_cpacs_file.save(filename)
new_cpacs_file.save(output_file)
