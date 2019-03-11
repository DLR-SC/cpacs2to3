import logging
import os

from . import tixi_helper


class UIDManager(object):
    def __init__(self):
        self.uids = set()
        self.invalid_uids = []
        self.empty_uid_paths = []

    def create_uid(self, tixi_handle, current_path):
        parent_uid, elem = tixi_helper.next_parent_uid(tixi_handle, current_path)

        new_uid = self.__make_unique_uid("%s_%s" % (parent_uid, elem))
        self.register_uid(new_uid)
        return new_uid

    def __make_unique_uid(self, proposed_uid):
        counter = 1
        new_uid = "%s%d" % (proposed_uid, counter)
        while self.uid_exists(new_uid):
            counter += 1
            new_uid = "%s%d" % (proposed_uid, counter)
        return new_uid

    def register_uid(self, uid):
        """
        Register an existing uid at the generator
        This is, to make sure this uid won't generated
        to avoid duplication of UIDs.
        :param uid:
        """

        if self.uid_exists(uid):
            raise RuntimeError('Duplicate UID: "%s"' % uid)

        self.uids.add(uid)

    def uid_exists(self, uid):
        return uid in self.uids

    def register_all_uids(self, tixi_handle):
        """
        Gets all elements with uiDs and registers them
        :param tixi_handle:
        """

        self.invalid_uids = []
        self.empty_uid_paths = []
        self.uids = set()

        logging.info("Registering all uIDs")
        paths = tixi_helper.resolve_xpaths(tixi_handle, "/cpacs/vehicles//*[@uID]")
        for elem in paths:
            uid = tixi_handle.getTextAttribute(elem, "uID")
            if uid == "":
                self.empty_uid_paths.append(elem)
            else:
                try:
                    uid_manager.register_uid(uid)
                except RuntimeError:
                    self.invalid_uids.append(uid)

        self.invalid_uids = list(sorted(set(self.invalid_uids)))

    def __fix_duplicate_uid(self, tixi_handle, uid):
        """
        Fixed a duplicate uid in the cpacs file

        :param tixi_handle: Handle to cpacs file
        :param uid: possibly duplicate uid
        """
        uid_paths = (tixi_helper.resolve_xpaths(tixi_handle, "//*[@uID='%s']" % uid))
        if len(uid_paths) <= 1:
            return

        text_paths_match_uid = (tixi_helper.resolve_xpaths(tixi_handle, "//*[text()='%s']" % uid))

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
            new_uid = self.create_uid(tixi_handle, uid_path)
            logging.info ("Renaming duplicate uid='%s' to '%s'" % (uid, new_uid))
            tixi_handle.removeAttribute(uid_path, "uID")
            tixi_handle.addTextAttribute(uid_path, "uID", new_uid)
            for text_path in text_paths:
                tixi_handle.updateTextElement(text_path, new_uid)

    def fix_invalid_uids(self, tixi_handle):
        """
        Fixed invalid uids in the file

        :param tixi_handle: cpacs file handle
        """

        for elem in self.empty_uid_paths:
            new_uid = uid_manager.create_uid(tixi_handle, elem)
            logging.info('Replacing empty uid with "%s"' % new_uid)
            tixi_handle.removeAttribute(elem, "uID")
            tixi_handle.addTextAttribute(elem, "uID", new_uid)

        if len(self.invalid_uids) > 0:
            logging.warning("There are duplicate uIDs in the data set!")
        for uid in self.invalid_uids:
            self.__fix_duplicate_uid(tixi_handle, uid)

        if len(self.invalid_uids) > 0 or len(self.empty_uid_paths) > 0:
            return True
        else:
            return False


uid_manager = UIDManager()
