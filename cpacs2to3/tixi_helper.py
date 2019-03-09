import logging
import os

from tixi3.tixi3wrapper import Tixi3Exception
from cpacs2to3.uid_generator import uidGenerator


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


def fix_duplicate_uid(tixi_handle, uid):
    """
    Fixed a duplicate uid in the cpacs file

    :param tixi_handle: Handle to cpacs file
    :param uid: possibly duplicate uid
    """
    uid_paths = (resolve_xpaths(tixi_handle, "//*[@uID='%s']" % uid))
    if len(uid_paths) <= 1:
        return

    text_paths_match_uid = (resolve_xpaths(tixi_handle, "//*[text()='%s']" % uid))

    uid_map = {}
    for uid_path in uid_paths:
        uid_map[uid_path] = []

    # for each of the text nodes, select those uid that has the longest parent node
    # map these text_node -> uid node
    for text_node_path in text_paths_match_uid:

        longest_str = ""
        longest_uid_path = ""
        for uid_path in uid_paths:
            substring = os.path.commonprefix([uid_path, text_node_path])
            if len(substring) > len(longest_str):
                longest_str = substring
                longest_uid_path = uid_path

        uid_map[longest_uid_path].append(text_node_path)

    for uid_path, text_paths in uid_map.items():
        new_uid = uidGenerator.create(tixi_handle, uid_path)
        logging.info ("Renaming duplicate uid='%s' to '%s'" % (uid, new_uid))
        tixi_handle.removeAttribute(uid_path, "uID")
        tixi_handle.addTextAttribute(uid_path, "uID", new_uid)
        for text_path in text_paths:
            tixi_handle.updateTextElement(text_path, new_uid)


def fix_invalid_uids(empty_uids_paths, duplicate_uids, tixi_handle):
    """
    Fixed invalid uids in the file

    :param empty_uids_paths: unique paths of element with an empty uid
    :param duplicate_uids: list of uids that are duplicate

    :param tixi_handle: cpacs file handle
    """

    for elem in empty_uids_paths:
        new_uid = uidGenerator.create(tixi_handle, elem)
        logging.info('Replacing empty uid with "%s"' % new_uid)
        tixi_handle.removeAttribute(elem, "uID")
        tixi_handle.addTextAttribute(elem, "uID", new_uid)

    if len(duplicate_uids) > 0:
        logging.warning("There are duplicate uIDs in the data set!")
    for uid in duplicate_uids:
        fix_duplicate_uid(tixi_handle, uid)


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
