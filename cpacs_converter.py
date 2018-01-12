from tigl import tiglwrapper
from tigl3 import tigl3wrapper

from tixi3 import tixi3wrapper
from tixi import tixiwrapper

from datetime import datetime

class UIDGenerator(object):
    def __init__(self):
        self.counter = 0

    def create(self):
        self.counter += 1
        return "uid_%d" % self.counter

uidGenerator = UIDGenerator()

def changeCpacsVersion(tixi3):
    tixi3.updateTextElement("/cpacs/header/cpacsVersion", "3.0")

def add_changelog(tixi3):
    if not tixi3.checkElement("/cpacs/header/updates"):
        tixi3.createElement("/cpacs/header", "updates")

    tixi3.createElement("/cpacs/header/updates", "update")
    n_updates = tixi3.getNamedChildrenCount("/cpacs/header/updates", "update")
    xpath = "/cpacs/header/updates/update[%d]" % n_updates
    tixi3.addTextElement(xpath, "modification", "Converted to cpacs 3.0 using cpacs2to3")
    tixi3.addTextElement(xpath, "creator", "cpacs2to3")
    tixi3.addTextElement(xpath, "timestamp", datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))
    tixi3.addTextElement(xpath, "version", "ver1")
    tixi3.addTextElement(xpath, "cpacsVersion", "3.0")


def getAllPathsMatching(tixi3, xpath):
    n_nodes = tixi3.xPathEvaluateNodeNumber(xpath)
    paths = []
    for i in range(0, n_nodes):
        paths.append(tixi3.xPathExpressionGetXPath(xpath, i+1))
    return paths

def add_uid(tixi3, xpath, uid):
    if not tixi3.checkElement(xpath):
        return
    if not tixi3.checkAttribute(xpath, "uID"):
        tixi3.addTextAttribute(xpath, "uID", uid)

def add_missing_uids(tixi3):
    paths = getAllPathsMatching(tixi3, "//transformation")
    for path in paths:
        add_uid(tixi3, path, uidGenerator.create())
        add_uid(tixi3, path + "/rotation", uidGenerator.create())
        add_uid(tixi3, path + "/scaling", uidGenerator.create())
        add_uid(tixi3, path + "/translation", uidGenerator.create())

    xpaths = ['//positioning', '//lowerShell', '//upperShell', '//rotorBladeAttachment']
    for xpath in xpaths:
        try:
            paths = getAllPathsMatching(tixi3, xpath)
            for path in paths:
                add_uid(tixi3, path, uidGenerator.create())
        except:
            pass

def get_new_cs_coordinates(tigl2, tigl3, compseg_uid, eta_old, xsi_old):
    px, py, pz = tigl2.wingComponentSegmentGetPoint(compseg_uid, eta_old, xsi_old)
    return tigl3.wingComponentSegmentPointGetEtaXsi(compseg_uid, px, py, pz)

old_cpacs_file = tixiwrapper.Tixi()
new_cpacs_file = tixi3wrapper.Tixi3()

filename = "simple_test_rotors.cpacs.xml"
output_file = "simple_test_rotors_old.cpacs.xml"

old_cpacs_file.open(filename)
new_cpacs_file.open(filename)
# new_cpacs_file.usePrettyPrint(1)

# perform structural changes
changeCpacsVersion(new_cpacs_file)
add_missing_uids(new_cpacs_file)
add_changelog(new_cpacs_file)

tigl2 = tiglwrapper.Tigl()
tigl2.open(old_cpacs_file, "")

tigl3 = tigl3wrapper.Tigl3()
tigl3.open(new_cpacs_file, "")

old_cpacs_file.save(output_file)
new_cpacs_file.save(filename)