"""
Simple graph implementation.
I am experimenting before putting it into pakit.

Adjacency list makes sense due to sparse nature of package
dependencies & python support for lists.
"""
from __future__ import absolute_import, print_function


class CycleInGraphError(Exception):
    """
    There was a cycle in the graph.
    """
    pass


class Vertex(object):
    """
    A simple vertex object.
    """
    def __init__(self, name):
        self.name = name
        self.was_visited = False

    def __str__(self):
        return self.name + ' was visited: ' + str(self.was_visited)


class Graph(object):
    """
    Repesents an undirected graph with adjacency list.
    """
    def __init__(self, max_verts):
        self.vertex_list = []
        self.adj_list = [[] for _ in range(max_verts)]

    def __str__(self):
        msg = 'The vertex list has: {0} elements\n'.format(self.num_verts)
        msg += '\n'.join([str(vert) for vert in self.vertex_list])
        msg += '\n\nThe adjacency list is:\n'
        adj_lines = [str(ind) + ': ' + ', '.join([str(num) for num in line])
                     for ind, line in enumerate(self.adj_list)]
        msg += '\n'.join(adj_lines) + '\n'
        return msg

    def __contains__(self, vert):
        return vert in [n_vert.name for n_vert in self.vertex_list]

    @property
    def num_verts(self):
        """
        Max number of verts in graph.
        """
        return len(self.vertex_list)

    def add_vertex(self, vert_name):
        """
        Add a vertex to the graph.
        """
        self.vertex_list.append(Vertex(vert_name))

    def add_edge(self, start, end):
        """
        Start and end are positional indexes into vertex list.
        """
        self.adj_list[start].append(end)
        self.adj_list[end].append(start)

    def display_vertex(self, pos):
        """
        Show a vertex at the position.
        """
        print(self.vertex_list[pos])

    def is_connected(self, start, end):
        """
        Returns true iff start has an edge to end.
        """
        return end in self.adj_list[start]

    def get_unvisited_adjacent(self, v_index):
        """
        Get first position connected to v_index that has NOT
        been visited before.

        Returns:
            A position of a vertex in vertex_list, else -1 if None found.
        """
        for pos in self.adj_list[v_index]:
            if not self.vertex_list[pos].was_visited:
                return pos

        return -1

    def remove(self, v_index):
        """
        Remove all trace of vertex at v_index.
        """
        for a_list in self.adj_list:
            try:
                a_list.remove(v_index)
            except ValueError:
                pass
        del self.adj_list[v_index]
        del self.vertex_list[v_index]


class DiGraph(Graph):
    """
    Directed graph.
    """
    def add_edge(self, start, end):
        """
        Start and end are positional indexes into vertex list.
        """
        self.adj_list[start].append(end)


def bfs_search(graph, func, start_pos):
    """
    BFS Search, on unvisited nodes pass to func.

    Args:
        graph: A graph.Graph instance.
        func: A function of form func(vertex)
        start_pos: An index in the vertex_list of g.
    """
    queue = [start_pos]
    vert = graph.vertex_list[start_pos]
    func(vert)
    vert.was_visited = True

    while len(queue):
        adjacent = graph.get_unvisited_adjacent(queue[-1])
        if adjacent != -1:
            queue.insert(0, adjacent)
            vert = graph.vertex_list[adjacent]
            func(vert)
            vert.was_visited = True
        else:
            queue.pop()


def dfs_search(graph, func, start_pos):
    """
    DFS Search, on unvisited nodes pass to func.

    Args:
        graph: A graph.Graph instance.
        func: A function of form func(vertex)
        start_pos: An index in the vertex_list of g.
    """
    stack = [start_pos]
    vert = graph.vertex_list[start_pos]
    func(vert)
    vert.was_visited = True

    while len(stack):
        adjacent = graph.get_unvisited_adjacent(stack[-1])
        if adjacent != -1:
            stack.append(adjacent)
            vert = graph.vertex_list[adjacent]
            func(vert)
            vert.was_visited = True
        else:
            stack.pop()


def mst_search(graph, func, start_pos):
    """
    MST creation, prints edges needed for an MST.

    Args:
        graph: A graph.Graph instance.
        func: A function of form func(vertex_a, vertex_b)
        start_pos: An index in the vertex_list of g.
    """
    stack = [start_pos]
    vert = graph.vertex_list[start_pos]
    vert.was_visited = True

    while len(stack):
        prev_vert = graph.vertex_list[stack[-1]]
        adjacent = graph.get_unvisited_adjacent(stack[-1])
        if adjacent != -1:
            stack.append(adjacent)
            vert = graph.vertex_list[adjacent]
            func(prev_vert.name, vert.name)
            vert.was_visited = True
        else:
            stack.pop()


def topo_list(graph):
    """
    Topological sort of graph.

    Returns:
        A list in sorted order.

    Raises:
        CycleInGraphError: The directed graph had a cycle.
    """
    # FIXME: Need to change adj_list to index on string keys.
    #        When deleting, int positions become stale refs.
    #        Works if I go from back for now.
    t_list = []

    last_len = len(graph.vertex_list)
    while len(graph.vertex_list) != 0:
        print(graph)
        for ind in range(graph.num_verts - 1, -1, -1):
            vert = graph.vertex_list[ind]
            adj_list = graph.adj_list[ind]

            if len(adj_list) == 0:
                print('Select:', vert, adj_list)
                t_list.append(vert.name)
                graph.remove(ind)
                break

        print(t_list)
        new_len = len(graph.vertex_list)
        if last_len == new_len:
            print(graph)
            raise CycleInGraphError
        last_len = new_len

    return t_list
