import re

class Graph:
    def __init__(self):
        self.__g = {}

    def add_edge(self, node1, node2, **kwargs):
        edge = Edge(**kwargs)

        if node1 not in self.__g:
            self.__g[node1] = {}

        self.__g[node1][node2] = edge

    def get_edge(self, node1, node2):
        res = self.__g.get(node1)
        if res is None:
            return None

        edge = res.get(node2)
        return edge

    def has_key(self, node):
        res = self.__g.get(node)
        return res is not None

    def get_node(self, id):
        return self.__g[id]

    def find_path(self, start, end, path=[]):
        path = path + [start]
        if start == end:
            return path
        if not self.has_key(start):
            return None
        for node, edge in self.__g[start].items():
            if node not in path:
                new_path = self.find_path(node, end, path)
                if new_path:
                    return new_path
        return None


class Edge:
    def __init__(self, **kwargs):
        for a in kwargs.items():
            self.__setattr__(a[0], a[1])


class CPACS2Node:
    def __init__(self):
        pass

    def matches(self, other):
        match = re.match("[2].[0-9](.[0-9])?", other)
        return match is not None


class CPACS3Node:
    def __init__(self, major_version_str):
        self.major_version = major_version_str

    def matches(self, other):
        return other.startswith(self.major_version)