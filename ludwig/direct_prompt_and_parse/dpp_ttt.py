from .imports import *
from .dpp import DirectPromptingPlusParse
from typing import List
from collections import deque


def extract_python_code(text:str) -> List[str]:
    """
    Given a string `text` that may contain Python code blocks in the form:
        ```python
        # some code...
        ```
    return a list of the code blocks (as strings) without the backticks.
    """
    # Regex to match: ```python ... ``` including newlines.
    # The (.*?) is a "non-greedy" match, and re.DOTALL allows '.' to match newlines.
    pattern = re.compile(r"```python(.*?)```", re.DOTALL)
    # Find all matches
    matches = pattern.findall(text)
    # Each element in `matches` will be the code between the ```python and the closing ```
    return [m.strip() for m in matches]

@fig.component('direct-prompting')
class DPPforTicTacToe(DirectPromptingPlusParse):
	def __init__(self, search_type:str, **kwargs):
		"""	Direct prompting strategy applied on tic-tac-toe."""
		# P1
		st_template = ('{c_sys}\nYour implementation should comprise of a single python function "expand" which given the '
					   'state of the game (specify what state) representation should be used), it will return a '
					   'list of all possible next states. Crucially, the function ‘expand’ should only take one '
					   'input representing the current state, and output a list of states each of which could be'
					   ' passed into ‘expand’ without error. Return an empty list if there are no possible next '
					   'states.')
		# P2
		state_desc_template = ('{c_sys}\nDescribe the specification of the state representation that "expand" expects such that '
							 'a person could, given a description of a state, represent it in the desired format '
							 'to apply the ‘expand’ function.\n{desc_f}')
		# P3
		init_state_est_tempalte = ('{c_task}\n {c_query}\n But first, identify the state of the game using the following '
								 'format:\n{desc_x}\nDescribe the state of the game in the format that the ‘expand’ '
								 'function expects so that we can apply search to help you answer the question '
								 'subsequently. You don\'t need to answer the question yet, just specify the correct'
								 ' state for now.')
		# P4
		info_extractor_prompt = ('{c_task}\nThe overall goal is to answer this question:\n{c_query} However, for now, '
								 f'you should only implement a very specific python function called ‘evaluate’ '
								 f'that to help you answer the question. This ‘evaluate’ function should take a '
								 f'sequence of states (as a list) as input where each state has this specification:\n'
								 '{desc X} The "evaluate" function should return either None, if the sequence of '
								 f'states is not useful for answering the question, for example, because it is '
								 f'irrelevant. Otherwise, if some aspect of the trajectory is useful for answering '
								 f'the question, then ‘evaluate’ should analyze the trajectory and extract that '
								 f'information and return it in a readily interpretable message. Note that the '
								 f'sequence of states is always ordered from a initial state to the current state '
								 f'being considered by the search algorithm. If None is returned the search continues '
								 f'trying to expand the trajectory further, otherwise the search terminates and the '
								 f'extracted information is used to answer the question. Since multiple rollouts may'
								 f' terminate with a message, make sure only to return a message if it is relevant '
								 f'to the question being asked, otherwise let the search continue. However, the '
								 f'search will only return this extracted information, so if any part of the '
								 f'trajectory contains useful info, be sure to include that.')
		# P5
		response_template = ('{c_task} The overall goal is to answer this question:\n{c_query} When applying a search '
						    'algorithm to this problem, the search has resulted in this log of information after'
						    ' traversing the state space:\n{trajectory}\nGiven this information, what is your answer '
						    'to the question? Answer concisely, no yapping.')
		super().__init__(st_template=st_template, state_desc_template=state_desc_template,
						 init_state_est_template=init_state_est_tempalte, info_extractor_template=info_extractor_prompt,
						 response_template=response_template, **kwargs)
		if search_type.upper() in ['BFS', 'DFS']:
			self.search_type = search_type.lower()
		else:
			raise ValueError(f'Searchtype: {search_type.upper()} not found. Possibilities are "BFS" and "DFS"')


		# We'll store a frontier of (node, path_to_node).
		# For BFS, this is a queue (deque), for DFS, we'll treat it like a stack (list).
		if self.search_type == 'BFS':
			self.frontier = deque()
		else:
			self.frontier = []

		# The "trajectory" is our current path from the root to the node
		# we are currently expanding.
		self.trajectory = []

		# Track the current node we are expanding.
		self.current_node = None

		# Just for clarity, we can store the "start" node if needed:
		self.start_node = None

	def initialize_search(self, start_node):
		"""
        Set the start node and prepare to begin searching.
        """
		self.start_node = start_node
		self.trajectory = [start_node]
		self.current_node = start_node

		# Clear and add (start_node, [start_node]) to frontier
		if self.search_type == 'bfs':
			self.frontier.clear()
			self.frontier.append((start_node, [start_node]))
		else:
			self.frontier = []
			self.frontier.append((start_node, [start_node]))

	def parse_info_extractor_function(self, desc_g) -> str:
		"""Extract the python implementation of infoextractor function of tic-tac-toe given an LLM response"""
		f_code = extract_python_code(desc_g)
		if len(f_code) == 0:
			raise ValueError('No python code found in provided description')
		elif len(f_code) > 1:
			raise ValueError('Too many python code blocks in description')
		else:
			return f_code[0]

	def parse_state_transition_function(self, desc_f) -> str:
		"""Extract the python implementation of state transition function of tic-tac-toe given an LLM response"""
		f_code = extract_python_code(desc_f)
		if len(f_code) == 0:
			raise ValueError('No python code found in provided description')
		elif len(f_code) > 1:
			raise ValueError('Too many python code blocks in description')
		else:
			return f_code[0]

	def parse_state(self, desc_x:str) -> str:
		"""Assume desc_x is identical as x"""
		return desc_x

	def choose_to_expand(self, x_js):
		"""
        x_js: the *neighbors* (children) of the current node.

        - If BFS, we add these neighbors to the queue.
        - If DFS, we add these neighbors to the stack.
        - Then we pick the next node to expand from the frontier:
            * BFS => pop from the left of the queue
            * DFS => pop from the right of the stack
        - If in DFS mode and x_js is empty, it means a dead end:
            * We 'backtrack' by removing the last node from self.trajectory
            * Then we pick the next from the frontier (if any)
        - We update self.current_node and self.trajectory to the chosen node's path.
        - Return the newly chosen node (or None if frontier is empty).
        """
		if self.search_type == 'DFS':
			# If no neighbors, that means a dead-end in DFS => backtrack right away
			if not x_js:
				if self.trajectory:
					_removed = self.trajectory.pop()  # backtrack from current
				# You might print/log the backtrack step here if desired
			# We'll pick the next node from the frontier below
			else:
				# Add each neighbor to the DFS frontier
				for nbr in x_js:
					new_path = self.trajectory + [nbr]
					self.frontier.append((nbr, new_path))
		else:
			# BFS: we don't do step-by-step backtracking. We just queue new neighbors.
			for nbr in x_js:
				new_path = self.trajectory + [nbr]
				self.frontier.append((nbr, new_path))

		# Now pick the next node to expand from the frontier
		if self.frontier:
			if self.search_type == 'BFS':
				# pop from the left
				next_node, next_path = self.frontier.popleft()
			else:
				# DFS => pop from the right
				next_node, next_path = self.frontier.pop()

			self.current_node = next_node
			self.trajectory = next_path
			return next_node
		else:
			# Frontier is empty => no more nodes to expand
			self.current_node = None
			self.trajectory = []
			return None

