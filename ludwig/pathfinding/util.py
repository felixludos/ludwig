from ..imports import *
from ..base import TaskBase
from ..util import ToolError, repo_root

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
		return self

	def get_current_graph(self):
		raise NotImplementedError
