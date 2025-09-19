from ..imports import *
from ..util import ToolBase, ToolError

import networkx as nx
from .util import all_paths



@fig.component('path/tool/graph')
class GraphPaths(ToolBase):
	@property
	def name(self) -> str:
		return 'all_paths_in_graph'

	def description(self) -> str:
		return ('A tool to find all paths between two nodes in an undirected graph. Returns a list of paths, '
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

		if not isinstance(nodes, list):
			raise ToolError('Nodes must be a list')
		if not all(isinstance(n, str) for n in nodes):
			raise ToolError('All nodes must be strings')
		if not isinstance(edges, list):
			raise ToolError('Edges must be a list')
		if not all(isinstance(e, list) and len(e) == 2 and all(isinstance(n, str) for n in e) for e in edges):
			raise ToolError('All edges must be lists of two strings')
		if not isinstance(source, str):
			raise ToolError('Source must be a string')
		if source not in nodes:
			raise ToolError(f'Source node {source!r} not in nodes')
		if not isinstance(target, str):
			raise ToolError('Target must be a string')
		if target not in nodes:
			raise ToolError(f'Target node {target!r} not in nodes')
		if source == target:
			raise ToolError('Source and target nodes must be different')

		G = nx.Graph()
		G.add_nodes_from(nodes)
		G.add_edges_from(edges)
		if not nx.has_path(G, source, target):
			raise ToolError(f'No path between {source!r} and {target!r}')
		paths = all_paths(G, source, target)
		return json.dumps(paths)



@fig.component('path/tool/finding')
class FindPaths(ToolBase):
	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self._task = None

	def prepare(self, task: 'PathTask'):
		self._task = task
		return self

	@property
	def name(self) -> str:
		return 'find_all_paths'

	def description(self) -> str:
		return ('A tool to find paths between two nodes in the graph of the given story. Returns a list of paths, '
				'where each path is represented as a list of node identifiers starting from the source node '
				'and ending at the target node. If there are no paths, return an empty list.')

	def schema(self, style: str = None) -> JSONOBJ:
		return {
			"type": "function",
			"function": {
				"name": self.name,
				"description": self.description(),
				"parameters": {
					"type": "object",
					"properties": {
						"source": {
							"type": "string",
							"description": "The identifier of the starting node."
						},
						"target": {
							"type": "string",
							"description": "The identifier of the target node."
						}
					},
					"required": ["source", "target"],
				}
			}
		}

	def call(self, arguments: JSONOBJ, *, seed: Optional[int] = None) -> str:
		assert isinstance(arguments, dict), f'Invalid arguments type: {arguments}'
		source = arguments.get('source', None)
		target = arguments.get('target', None)

		if self._task is None:
			raise ValueError(f'This tool has not been prepared with a PathTask before use.')
		graph = self._task.get_current_graph()

		if not isinstance(source, str):
			raise ToolError('Source must be a string')
		if source not in graph.nodes():
			raise ToolError(f'Source node {source!r} not in nodes')
		if not isinstance(target, str):
			raise ToolError('Target must be a string')
		if target not in graph.nodes():
			raise ToolError(f'Target node {target!r} not in nodes')

		paths = all_paths(graph, source, target)
		return json.dumps(paths)

