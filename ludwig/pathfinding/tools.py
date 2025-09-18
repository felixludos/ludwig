from ..imports import *
from ..util import ToolBase, ToolError, repo_root

import itertools
import networkx as nx


def to_graph(item):
	edges = item['task1']['target']
	G = nx.Graph()
	for s, e in edges:
		G.add_edge(s, e)
	return G


def generate_candidates(G):
	distances = dict(nx.floyd_warshall(G))
	nodes = list(G.nodes())

	for a, b in itertools.permutations(nodes, 2):
		if distances[a][b] >= 2:
			yield a, b


def all_paths(G, source, target):
	return list(nx.all_simple_paths(G, source=source, target=target))


def unused_nodes(G, path):
	for node in G.nodes():
		if node not in path:
			yield node


def path_nodes(G, a, b):
	used = {n for path in all_paths(G, a, b) for n in path if n != a and n != b}
	unused = {n for n in G.nodes() if n not in used and n != a and n != b}
	return used, unused


def select_paths(G):
	tbl = [[a, b, *path_nodes(G, a, b)] for a, b in generate_candidates(G)]
	tbl = sorted(tbl, key=lambda x: (abs(len(x[2]) - len(x[3])), len(x[0]) + len(x[1])))
	assert len(tbl)
	best = [item for item in tbl if abs(len(item[2]) - len(item[3])) == abs(len(tbl[0][2]) - len(tbl[0][3]))]
	return best



@fig.component('path/tool/finding')
class Pathfinding(ToolBase):
	@property
	def name(self) -> str:
		return 'path_finder'

	def description(self) -> str:
		return ('A tool to find a path between two nodes in an undirected graph. Returns a list of paths, '
				'where each path is represented as a list of node identifiers starting from the source node '
				'and ending at the target node.')

	def schema(self, style: str = None) -> JSONOBJ:
		return {
			"type": "function",
			"function": {
				"name": self.name,
				"description": self.description(),
				"parameters": {
					"type": "object",
					"properties": {
						"nodes": {
							"type": "array",
							"description": "A list of node identifiers representing the undirected graph.",
						},
						"edges": {
							"type": "array",
							"description": "A list of edges, where each edge is represented as a tuple of two node identifiers.",
							"items": {"type": "array", "minItems": 2, "maxItems": 2, "items": {"type": "string"}}
						},
						"source": {
							"type": "string",
							"description": "The identifier of the starting node."
						},
						"target": {
							"type": "string",
							"description": "The identifier of the target node."
						}
					},
					"required": ["nodes", "edges", "source", "target"],
				}
			}
		}

	def call(self, arguments: JSONOBJ, *, seed: Optional[int] = None) -> str:
		assert isinstance(arguments, dict), f'Invalid arguments type: {arguments}'
		nodes = arguments.get('nodes', None)
		edges = arguments.get('edges', None)
		source = arguments.get('source', None)
		target = arguments.get('target', None)

		if not isinstance(nodes, list) or not all(isinstance(n, str) for n in nodes):
			raise ToolError('Invalid nodes list')
		if not isinstance(edges, list) or not all(isinstance(e, list) and len
(e) == 2 and all(isinstance(n, str) for n in e) for e in edges):
			raise ToolError('Invalid edges list')
		if not isinstance(source, str) or source not in nodes:
			raise ToolError('Invalid source node')
		if not isinstance(target, str) or target not in nodes:
			raise ToolError('Invalid target node')
		if source == target:
			raise ToolError('Source and target nodes must be different')
		G = nx.Graph()
		G.add_nodes_from(nodes)
		G.add_edges_from(edges)
		if not nx.has_path(G, source, target):
			raise ToolError(f'No path between {source!r} and {target!r}')
		paths = all_paths(G, source, target)
		return json.dumps(paths)


