import networkx as nx
import re

from ludwig.imports import *
from ludwig.causality.causal_task import CausalTask

PROBLEM = JSONDATA
ANSWER = JSONDATA


class isBackdoorAdjustment(CausalTask):
	def __init__(self,
			  n: int=5):
		super().__init__()
		self.dataset = None
		self.data_len = None
		self.n = n
	@property
	def name(self) -> str:
		return "causality-isBackdoorAdjustment"

	@property
	def total_questions(self) -> Optional[int]:
		return self.data_len

	def context(self) -> str:
		return ("Answer Yes or No to the question of "
		  "whether a set is a backdoor adjustment set to identify "
		  "the treatment effect between two given variables." 
		  "You will be given pairwise causal relations between variables")

	def description(self) -> str:
		return "We are analysing a causal graph and we find ourselves in the following situation."
	
	def generate(self, seed: int=42) -> Tuple[PROBLEM, ANSWER]:
		""" Sample a causal graph, choose a node randomly and choose a node among its ancestors.
		"""
		causal_pairs, causal_graph = self._generate_dag(seed=seed)

		# Sample whether we are taking a yes or no and, if no, implement taking two random nodes that are not an ancestor of each other
		yes = self.rng.binomial(1, 0.5) # yes = 1, no = 0 
		adjustment_set = None

		if yes==1: # Verify that this comparison is correct and not float vs. int.
			for i in self.rng.permutation(range(self.n)):
				ancestors = nx.ancestors(causal_graph, i)
				ancestors_no_parents = list(ancestors.difference(set(causal_graph.predecessors(i))))
				if len(ancestors)==0 or len(ancestors_no_parents)==0:
					continue
				else:
					j = self.rng.choice(ancestors_no_parents)
					adjustment_set = nx.find_minimal_d_separator(causal_graph, set([j]), set([i]))
					if adjustment_set == None:
						continue
					else:
						adjustment_set_tuple = (j, i, list(adjustment_set)) # variable_1, variable_2, adjustment set
						answer = "Yes"
						break
		else: # If we sampled a no from the beginning we look for a non-valid adjustment set
			for i in self.rng.permutation(range(self.n)):
				nodes = set(causal_graph)
				j = self.rng.choice(list(nodes.difference(set([i]))))
				n_adjustment_set = self.rng.choice(self.n-2) # All the possible nodes but i and j
				adjustment_set = self.rng.choice(list(nodes.difference(set([i,j]))), replace=False, size=n_adjustment_set) 
				if nx.is_d_separator(causal_graph, set([i]), set([j]), set(adjustment_set)) == True:
					continue
				else:
					adjustment_set_tuple = (j, i, adjustment_set) # variable_1, variable_2, adjustment set
					answer = "No"
					break
		
		if yes==1 and adjustment_set==None: # If we sampled yes but we couldn't find a valid adjustment set, we try for a no in any case
			for i in self.rng.permutation(range(self.n)):
				nodes = set(causal_graph)
				j = self.rng.choice(list(nodes.difference(set([i]))))
				n_adjustment_set = self.rng.choice(self.n-2) # All the possible nodes but i and j
				adjustment_set = self.rng.choice(list(nodes.difference(set([i,j]))), replace=False, size=n_adjustment_set) 
				if nx.is_d_separator(causal_graph, set([i]), set([j]), set(adjustment_set)) == True:
					adjustment_set_tuple = (j, i, adjustment_set) # variable_1, variable_2, adjustment set
					answer = "Yes"
					break
				else:
					adjustment_set_tuple = (j, i, adjustment_set) # variable_1, variable_2, adjustment set
					answer = "No"
					break

		assert not adjustment_set is None, "We could not find a valid task for these settings. Try another seed or size of graph."

		return (adjustment_set_tuple, causal_pairs), answer


	def observe(self, problem: List[str], *, seed: int = None) -> str:
		x_causes_y = lambda x, y: f"{x} causes {y}"
		y_is_effect_of_x = lambda x, y: f"{y} is the effect of {x}"
		x_arrow_y = lambda x, y: f"{x} -> {y}"
		
		causal_descriptors = [
			x_causes_y,
			y_is_effect_of_x,
			x_arrow_y
		]

		(variable_j, variable_i, adjustment_set), causal_pairs = problem

		causal_relations = [f(*x) for f, x in zip(self.rng.choice(causal_descriptors, size=len(causal_pairs)), causal_pairs)]
		causal_relation_string = ", ".join(causal_relations)
		template = (f"Here are some causal relations between variables named as integers {causal_relation_string}. "
			  f"Please answer with a Yes or No whether the set {adjustment_set} is a d-separating set of {variable_i} and {variable_j}")
		
		return template

	def correct(self, response: str, answer: bool) -> bool:
		raise NotImplementedError


if __name__ == '__main__':
	# Example usage:
	is_backdoor_adjustment = isBackdoorAdjustment()
	
	problem, answer = is_backdoor_adjustment.generate()
	
	print(f"Variables to check for adjustment set: {problem[0][0]}")
	print(f"Adjustment set: {problem[0][1]}")
	print(f"Causal pairs: {problem[1]}")
	print(answer)
