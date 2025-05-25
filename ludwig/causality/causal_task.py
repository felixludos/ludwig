from typing import Tuple, Union, Dict, List
import networkx as nx
import numpy as np
from numpy.random import default_rng

from ludwig.imports import *
from ludwig.base import TaskBase

PROBLEM = JSONDATA
ANSWER = JSONDATA


class CausalTask(TaskBase):
	"""Some other possible tasks, not currently implemented:
	- Check whether two marginal graphs are consistent with each other
	- Check whether a marginal graph can be produced from a DAG
	"""
	def __init__(self,
			  n: int=5):
		super().__init__()
		self.dataset = None
		self.data_len = None
		self.n = n
	
	def _generate_dag(self, seed: int=42) -> Tuple[PROBLEM, ANSWER]:
		# Initialize numpy random number generator with given seed
		self.rng = default_rng(seed=seed)

		p = 2*np.log(self.n)/self.n # Erdos-Renyi model to have connectivity with high probability
		
		graph = self.rng.binomial(1, p, size=(self.n, self.n))
		graph_wo_self_edges = graph - np.diag(np.diag(graph))
		adjacency_matrix_dag = np.triu(graph_wo_self_edges)

		causal_pairs = []
		for i in range(self.n):
			for j in range(i, self.n):
				if adjacency_matrix_dag[i,j] != 0:
					causal_pairs.append((i,j)) # cause-effect tuples

		nx_graph = self.causal_graph = nx.empty_graph(self.n, nx.DiGraph)
		nx_graph.add_edges_from(causal_pairs)

		return causal_pairs, nx_graph
	
	@staticmethod
	def draw_causal_graph(graph):
		raise NotImplementedError
	

if __name__ == '__main__':
	# Example usage:
	causal_task = CausalTask()
	causal_relations, graph = causal_task._generate_dag()
	
	print(causal_relations)
	print(graph)
