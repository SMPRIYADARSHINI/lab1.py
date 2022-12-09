
class Bellmanford(object):
    def __init__(self, graph):
        self.graph = graph
        self.edges = []
        self.distance = {}
        self.parent = {}
        self.negative_cycle = None

    def shortest_paths(self, start_vertex, tolerance=0):
        # create vertices list
        vertices = list(self.graph.keys())
        values = list(self.graph.values())
        for each_value in values:
            # dict(each_value)
            keys = each_value.keys()
            for each_key in keys:
                if each_key not in vertices:
                    vertices.append(each_key)

        # list of edges
        vertices_list = list(self.graph.keys())
        for vertex1 in vertices_list:   # vertex1 is from vertex
            value_dict = self.graph[vertex1]
            for vertex2 in value_dict:  # vertex2 is to vertex
                self.edges.append([vertex1, vertex2, value_dict[vertex2]])  # value_dict[vertex2] gives edge weigh

        # initializing the vertices weights and distances of graph
        for vertex in vertices:
            self.distance[vertex] = float('inf')
            self.parent[vertex] = None
        self.distance[start_vertex] = 0

        # Relax all edges |V|-1 times
        for _ in range(len(vertices)):
            for edge in self.edges:
                vertex1 = edge[0]
                vertex2 = edge[1]
                edge_weight = edge[2]
                if self.distance[vertex2] - (self.distance[vertex1] + edge_weight) > tolerance:
                    if vertex2 == start_vertex:
                        return self.distance, self.parent, (vertex1, vertex2)
                    self.distance[vertex2] = self.distance[vertex1] + edge_weight
                    self.parent[vertex2] = vertex1

        # Performing relax again to find negative cycle
        for edge in self.edges:
            vertex1 = edge[0]
            vertex2 = edge[1]
            edge_weight = edge[2]
            if vertex2 == start_vertex:
                if self.distance[vertex2] > self.distance[vertex1] + edge_weight:
                    self.negative_cycle = (vertex1, vertex2)
                    return self.distance, self.parent, self.negative_cycle
        return self.distance, self.parent, self.negative_cycle
