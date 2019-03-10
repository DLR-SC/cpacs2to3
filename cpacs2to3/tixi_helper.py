from tixi3.tixi3wrapper import Tixi3Exception

def resolve_xpaths(tixi_handle, xpath):
    """
    Returns all paths that match the given xpath
    :param tixi_handle: handle to tixi document
    :param xpath: the xpath that should be resolved
    :return: list of element paths
    """
    if xpath == '':
        return []

    try:
        n_nodes = tixi_handle.xPathEvaluateNodeNumber(xpath)
        paths = []
        for i in range(0, n_nodes):
            paths.append(tixi_handle.xPathExpressionGetXPath(xpath, i + 1))
        return paths
    except Tixi3Exception:
        return []


def parent_path(xpath):
    """
    Removes the last element in an xpath, effectively yielding the xpath to the parent element
    :param xpath: An xpath with at least one '/'
    """
    return xpath[:xpath.rfind('/')]


def split_parent_child_path(child_path):
    while child_path[-1] == '/':
        child_path = child_path[0:-1]
    pos = child_path.rindex('/')

    parent = child_path[0:pos]
    child = child_path[pos + 1:]

    pos = child.rfind("[")
    if pos > 0:
        child = child[0:pos]

    return parent, child


def element_name(element_path):
    """
    Gives the last element in an xpath
    :param element_path: An xpath with at least one '/'
    """
    return element_path[element_path.rfind('/') + 1:]


def element_index(tixi_handle, xpath):
    """
    Finds the index of the child element in the given xpath in its parent element
    :param tixi_handle: TiXI 3 handle
    :param xpath: An xpath with at least one '/'
    """
    parentXPath = parent_path(xpath)
    childName = element_name(xpath)
    count = tixi_handle.getNumberOfChilds(parentXPath)
    for i in range(count):
        if tixi_handle.getChildNodeName(parentXPath, i + 1) == childName:
            return i + 1
    return count


def next_parent_uid(tixi_handle, current_path):
    parent, elem = split_parent_child_path(current_path)
    while not tixi_handle.checkAttribute(parent, "uID"):
        parent, _ = split_parent_child_path(parent)
        if parent == '':
            break

    if parent != '':
        parent_uid = tixi_handle.getTextAttribute(parent, "uID")
    else:
        parent_uid = ''

    return parent_uid, elem
