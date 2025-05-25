import networkx as nx
import re

from ludwig.imports import *
from ludwig.causality.causal_task import CausalTask

PROBLEM = JSONDATA
ANSWER = JSONDATA


class isAncestor(CausalTask):
	def __init__(self,
			  n: int=5):
		super().__init__()
		self.dataset = None
		self.data_len = None
		self.n = n
	@property
	def name(self) -> str:
		return "causality-isAncestor"

	@property
	def total_questions(self) -> Optional[int]:
		return self.data_len

	def context(self) -> str:
		return ("Answer Yes or No to the question of "
		  "whether a variable is an ancestor of another in a causal graph." 
		  "You will be given pairwise causal relations between variables")

	def description(self) -> str:
		return "We are analysing a causal graph and we find ourselves in the following situation."
	
	def generate(self, seed: int=42) -> Tuple[PROBLEM, ANSWER]:
		""" Sample a causal graph, choose a node randomly and choose a node among its ancestors.
		"""
		causal_pairs, causal_graph = self._generate_dag(seed=seed)

		# Sample whether we are taking a yes or no and, if no, implement taking two random nodes that are not an ancestor of each other
		yes = self.rng.binomial(1, 0.5) # yes = 1, no = 0 

		if yes==1:
			for i in self.rng.permutation(range(self.n)):
				if len(nx.ancestors(causal_graph, i))==0:
					continue
				else:
					ancestor = self.rng.choice(list(nx.ancestors(causal_graph, i)))
					ancestor_pair = (i, ancestor) # variable, ancestor tuple
					answer = "Yes"
					break
		else:
			for i in self.rng.permutation(range(self.n)):
				not_ancestor_set = set(causal_graph).difference(nx.ancestors(causal_graph, i))
				if len(not_ancestor_set) == 0:
					continue
				else:
					not_ancestor = self.rng.choice(list(not_ancestor_set))
					ancestor_pair = (i, ancestor) # variable, ancestor tuple
					answer = "No"
					break

		assert not ancestor is None, "The graph is completely disconnected, there are no causal relations. Try another seed."

		return (ancestor_pair, causal_pairs), answer

	def observe(self, problem: List[str], *, seed: int = None) -> str:
		x_causes_y = lambda x, y: f"{x} causes {y}"
		y_is_effect_of_x = lambda x, y: f"{y} is the effect of {x}"
		x_arrow_y = lambda x, y: f"{x} -> {y}"
		
		causal_descriptors = [
			x_causes_y,
			y_is_effect_of_x,
			x_arrow_y
		]

		ancestor_pair, causal_pairs = problem

		causal_relations = [f(*x) for f, x in zip(self.rng.choice(causal_descriptors, size=len(causal_pairs)), causal_pairs)]
		causal_relation_string = ", ".join(causal_relations)
		template = (f"Here are some causal relations between variables named as integers {causal_relation_string}. "
			  f"Please answer with a Yes or No whether {ancestor_pair[1]} is an ancestor of {ancestor_pair[0]}.")
		
		return template

	def correct(self, response: str, answer: bool) -> bool:
		raise NotImplementedError


if __name__ == '__main__':
	# Example usage:
	is_ancestor = isAncestor()
	
	problem, answer = is_ancestor.generate()
	
	print(f"Ancestor pair: {problem[0]}")
	print(f"Causal pairs: {problem[1]}")
	print(answer)
