import random

from ..abstract import PROBLEM
from ..imports import *
from ..base import TaskBase
from ..util import ToolBase, ToolError, repo_root

import itertools
import networkx as nx



class PathTask(TaskBase):
	def __init__(self, data_path: Union[str, Path] = repo_root().joinpath('assets', 'plugh', 'plugh.json'),
				 **kwargs):
		data_path = Path(data_path)
		super().__init__(**kwargs)
		self._data_path = data_path
		self._data = None

	@staticmethod
	def download(path: Union[str, Path] = repo_root().joinpath('assets', 'plugh', 'plugh.json')):
		path = Path(path)
		if path.exists():
			return
		path.parent.mkdir(parents=True, exist_ok=True)
		url = 'https://github.com/altsoph/PLUGH/raw/refs/heads/main/plugh.json'
		import requests
		r = requests.get(url)
		if r.status_code != 200:
			raise ToolError(f"Failed to download data from {url}: {r.status_code}")
		with path.open('w') as f:
			f.write(r.text)

	def prepare(self, seed: Optional[int] = None) -> Any:
		super().prepare(seed)
		if not self._data_path.exists():
			raise FileNotFoundError(f"Data file not found: {self._data_path}")
		self._data = json.load(self._data_path.open('r'))

	@staticmethod
	def to_graph(item):
		edges = item['task1']['target']
		G = nx.Graph()
		for s, e in edges:
			G.add_edge(s, e)
		return G

	@staticmethod
	def generate_candidates(G):
		distances = dict(nx.floyd_warshall(G))
		nodes = list(G.nodes())

		for a, b in itertools.permutations(nodes, 2):
			if distances[a][b] >= 2:
				yield a, b

	@staticmethod
	def all_paths(G, source, target):
		return list(nx.all_simple_paths(G, source=source, target=target))

	@staticmethod
	def unused_nodes(G, path):
		for node in G.nodes():
			if node not in path:
				yield node

	@classmethod
	def path_nodes(cls, G, a, b):
		used = {n for path in cls.all_paths(G, a, b) for n in path if n != a and n != b}
		unused = {n for n in G.nodes() if n not in used and n != a and n != b}
		return used, unused

	@classmethod
	def select_paths(cls, G):
		tbl = [[a, b, *cls.path_nodes(G, a, b)] for a, b in cls.generate_candidates(G)]
		tbl = sorted(tbl, key=lambda x: (abs(len(x[2]) - len(x[3])), len(x[0]) + len(x[1])))
		assert len(tbl)
		best = [item for item in tbl if abs(len(item[2]) - len(item[3])) == abs(len(tbl[0][2]) - len(tbl[0][3]))]
		return best



@fig.component('ttt/take-the-middle')
class CanIAvoid(PathTask):
	@property
	def name(self) -> str:
		return f"Avoid"

	def show_keys(self) -> Iterator[str]:
		yield 'question'
		yield 'system'
		yield 'task'

	def store_keys(self) -> Iterator[str]:
		yield 'problem'
		yield 'question'
		yield 'answer'


	def prepare(self, seed: Optional[int] = None) -> Any:
		super().prepare(seed)

		for item in self._data:
			G = self.to_graph(item)
			paths = self.select_paths(G)
			if len(paths) == 0:
				continue
			item['candidates'] = paths






