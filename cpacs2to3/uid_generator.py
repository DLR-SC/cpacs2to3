from . import tixi_helper

class UIDGenerator(object):
    def __init__(self):
        self.counter = 0
        self.uids = set()

    def create(self, tixi_handle, current_path):
        parent_uid, elem = tixi_helper.next_parent_uid(tixi_handle, current_path)

        new_uid = self.make_unique_uid("%s_%s" % (parent_uid, elem))
        self.register(new_uid)
        return new_uid

    def make_unique_uid(self, proposed_uid):
        counter = 1
        new_uid = "%s%d" % (proposed_uid, counter)
        while self.uid_exists(new_uid):
            counter += 1
            new_uid = "%s%d" % (proposed_uid, counter)
        return new_uid

    def register(self, uid):
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



uidGenerator = UIDGenerator()
