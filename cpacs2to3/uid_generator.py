class UIDGenerator(object):
    def __init__(self):
        self.counter = 0
        self.uids = set()

    def create(self, tixi_handle, current_path):
        parent, elem = self.get_parent_child_path(current_path)
        while not tixi_handle.checkAttribute(parent, "uID"):
            parent, _ = self.get_parent_child_path(parent)
            if parent == '':
                break

        if parent != '':
            parent_uid = tixi_handle.getTextAttribute(parent, "uID")
        else:
            parent_uid = ''

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

    @staticmethod
    def get_parent_child_path(child_path):
        while child_path[-1] == '/':
            child_path = child_path[0:-1]
        pos = child_path.rindex('/')

        parent = child_path[0:pos]
        child = child_path[pos + 1:]

        pos = child.rfind("[")
        if pos > 0:
            child = child[0:pos]

        return parent, child


uidGenerator = UIDGenerator()
