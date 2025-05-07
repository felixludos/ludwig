import networkx as nx
import re

from ludwig.imports import *
from ludwig.causality.causal_task import CausalTask

PROBLEM = JSONABLE
ANSWER = JSONABLE


class isGraphConnected(CausalTask):
	def __init__(self,
			  n: int=5):
		super().__init__()
		self.dataset = None
		self.data_len = None
		self.n = n
	@property
	def name(self) -> str:
		return "causality-isGraphConnected"

	@property
	def total_questions(self) -> Optional[int]:
		return self.data_len

	def context(self) -> str:
		return ("Answer Yes or No to the question of "
		  "whether the following causal graph is connected or not." 
		  "You will be given pairwise causal relations between variables")

	def description(self) -> str:
		return "We are analysing a causal graph and we find ourselves in the following situation."
	
	def generate(self, seed: int=42) -> Tuple[PROBLEM, ANSWER]:
		""" Sample a causal graph, choose a node randomly and choose a node among its ancestors.
		"""
		causal_pairs, causal_graph = self._generate_dag(seed=seed)
		answer = "Yes" if nx.is_connected(causal_graph.to_undirected()) else "No"

		return causal_pairs, answer

	def observe(self, problem: List[str], *, seed: int = None) -> str:
		x_causes_y = lambda x, y: f"{x} causes {y}"
		y_is_effect_of_x = lambda x, y: f"{y} is the effect of {x}"
		x_arrow_y = lambda x, y: f"{x} -> {y}"
		
		causal_descriptors = [
			x_causes_y,
			y_is_effect_of_x,
			x_arrow_y
		]

		causal_pairs = problem

		causal_relations = [f(*x) for f, x in zip(self.rng.choice(causal_descriptors, size=len(causal_pairs)), causal_pairs)]
		causal_relation_string = ", ".join(causal_relations)
		template = (f"Here are some causal relations between variables named as integers {causal_relation_string}. "
			  f"Please answer with a Yes or No whether the graph is connected.")
		
		return template

	def correct(self, response: str, answer: bool) -> bool:
		raise NotImplementedError


if __name__ == '__main__':
	# Example usage:
	is_graph_connected = isGraphConnected()
	
	problem, answer = is_graph_connected.generate()
	
	print(f"Causal pairs: {problem[1]}")
	print(answer)
