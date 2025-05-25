from ..imports import *
from ..base import TaskBase
from ..util import ToolBase, ToolError, repo_root
from ..errors import ParsingError
import re


@fig.component('ttt/take-the-middle')
class TakeTheMiddle(TaskBase):
	@property
	def name(self) -> str:
		return "TTT-TakeTheMiddle"

	@property
	def total_questions(self) -> Optional[int]:
		return len(self._problem_data) * 2 * 2

	def context(self) -> str:
		return "Implement all the rules of tic-tac-toe."

	def description(self) -> str:
		return "We're playing tic-tac-toe, and I have some questions."

	def specification(self) -> JSONOBJ:
		return {'answer': 'yes/no'}

	_problem_data = [
		['bottom left', 'top-center', 'middle left', 'top left', 'the remaining bottom corner'],
		['top-center', 'bottom left', 'middle left', 'top left', 'on the right in the middle'],
		['the top right', 'left bottom', 'top middle', 'top left', 'the remaining bottom corner'],
		['left bottom corner', 'the right bottom corner', 'left middle', 'top-left', 'the last open corner'],
	]
	_answer_data = ['no', 'yes', 'no', 'yes']

	def load(self, index: int, *, seed: Optional[int] = None) -> Tuple[List[str], str]:
		# This is a placeholder implementation for demo purposes.
		base_idx = index % len(self._problem_data)
		rev_flags = index // len(self._problem_data)
		rev_1 = rev_flags % 2
		rev_2 = (rev_flags // 2) % 2

		base = self._problem_data[base_idx].copy()
		if rev_1:
			base[0], base[2] = base[2], base[0]
		if rev_2:
			base[1], base[3] = base[3], base[1]

		return base, self._answer_data[base_idx]

	def observe(self, problem: List[str], *, seed: int = None) -> str:
		# This is a placeholder implementation for demo purposes.
		template = ("Alice started with {0} and I played {1}. She took {2}, so I responded with {3}. "
					"Now Alice played at {4}. I think I should play in the center-middle "
					"because it's a good spot in general. "
					"Is that my best move?")
		return template.format(*problem)



class TTT_Tool(ToolBase):
	def __init__(self, rep_type: str = 'nested', **kwargs):
		assert rep_type in ('str', 'list', 'nested'), f'Invalid representation type: {rep_type}'
		super().__init__(**kwargs)
		self.rep_type = rep_type

	def decode(self, state: JSONDATA) -> str:
		"""
		Decode the state string into a string.
		"""
		if self.rep_type == 'str':
			return state
		elif self.rep_type == 'list':
			return ''.join(state)
		elif self.rep_type == 'nested':
			return ''.join(''.join(row) for row in state)
		else:
			raise ValueError(f"Unknown representation type: {self.rep_type}")

	def encode(self, state: str) -> JSONDATA:
		"""
		Encode the state string into the specified representation.
		"""
		if self.rep_type == 'str':
			return state
		elif self.rep_type == 'list':
			return list(state)
		elif self.rep_type == 'nested':
			return [list(state[i:i + 3]) for i in range(0, len(state), 3)]
		else:
			raise ValueError(f"Unknown representation type: {self.rep_type}")

	def validate(self, state: JSONDATA) -> Optional[str]:
		"""
		Validate the state string.
		"""
		if self.rep_type == 'str':
			if not isinstance(state, str) or len(state) != 9:
				return "State must be a string of length 9."
			if not all(c in 'XO ' for c in state):
				return "State can only contain 'X', 'O', or ' '."
		elif self.rep_type == 'list':
			if not isinstance(state, list) or len(state) != 9:
				return "State must be a list of length 9."
			if not all(c in ['X', 'O', ' '] for c in state):
				return "State can only contain 'X', 'O', or ' '."
		elif self.rep_type == 'nested':
			if not isinstance(state, list) or len(state) != 3:
				return "State must be a list of 3 lists."
			for row in state:
				if len(row) != 3:
					return "Each row must have exactly 3 elements."
				if not all(c in ['X', 'O', ' '] for c in row):
					return "State can only contain 'X', 'O', or ' '."
		else:
			raise ValueError(f"Unknown representation type: {self.rep_type}")

	def _representation_schema(self) -> JSONOBJ:
		if self.rep_type == 'str':
			return {
				"type": "string",
				"description": "The state of the tic-tac-toe board as a string of 9 characters ('X', 'O', ' '). "
							   "The first 3 characters represent the first row, the next 3 the second row, "
							   "and the last 3 the third row.",
			}
		elif self.rep_type == 'list':
			return {
				"type": "array",
				"description": "The state of the tic-tac-toe board as a list of 9 characters.",
				"items": {
					"type": "string",
					"description": "The value of the cell, either 'X', 'O', or ' ' (empty).",
					"enum": ["X", "O", " "],
				}
			}
		elif self.rep_type == 'nested':
			return {
				"type": "array",
				"description":
					"The state of the tic-tac-toe board, represented as a list of 3 lists "
					"each corresponding to a row of the board from top to bottom. ",
				"items": {
					"type": "array",
					"description": "A row of the tic-tac-toe board with 3 cells "
								   "corresponding to the columns.",
					"items": {
						"type": "string",
						"description": "The value of the cell, either 'X', 'O', or ' ' (empty).",
						"enum": ["X", "O", " "],
					},
				},
			}
		else:
			raise ValueError(f"Unknown representation type: {self.rep_type}")



@fig.component('ttt/tool/value')
class StateValue(TTT_Tool):
	def __init__(self, val_type: str = 'minimax', **kwargs):
		assert val_type in ('minimax', 'expectimax'), f'Invalid value type: {val_type}'
		super().__init__(**kwargs)
		self.val_type = val_type

		path = repo_root().joinpath('assets', 'ttt', f'{val_type}.json')
		if not path.exists():
			raise FileNotFoundError(path)
		self.state_values = json.load(path.open('r'))

	@property
	def name(self) -> str:
		return 'state_value'

	def description(self) -> str:
		# return ('Evaluate the state of the tic-tac-toe board (assuming "X" always goes first). '
		# 		'Where positive means the board state favors "X", negative means the board state favors "O", '
		# 		'and 0 is a draw.')
		return ('Evaluate the state of the tic-tac-toe board. '
				'Where, assuming best play, 1 means "X" can win (or has won), -1 means "O" can win (or has won), '
				'and 0 means the game will result in a draw (or it is a draw already).')


	def schema(self, style: str = None) -> JSONOBJ:
		return {
			"type": "function",
			"function": {
				"name": self.name,
				"description": self.description(),
				"parameters": {
					"type": "object",
					"properties": {
						"state": self._representation_schema(),
						"current_player": {
							"type": "string",
							"description": "The current player, either 'X' or 'O'.",
							"enum": ["X", "O"],
						}
					},
					"required": ["state", "current_player"]
				}
			}
		}

	def call(self, arguments: JSONOBJ, *, seed: Optional[int] = None) -> str:
		assert isinstance(arguments, dict), f'Expected a dict, got {type(arguments)}'
		if 'state' not in arguments:
			raise ToolError("Missing 'state' in arguments")
		if 'current_player' not in arguments:
			raise ToolError("Missing 'current_player' in arguments")
		state = arguments['state']
		current_player = arguments['current_player']
		if current_player not in ['X', 'O']:
			raise ToolError("Invalid current player. Must be 'X' or 'O'.")

		error = self.validate(state)
		if error:
			raise ToolError(error)

		code = self.decode(state)
		starting_player = 'X' if ((code.count('X') == code.count('O') and current_player == 'X')
								  or code.count('X') > code.count('O')) else 'O'

		if starting_player == 'O':
			code = code.replace('X', '_').replace('O', 'X').replace('_', 'O')

		if code not in self.state_values:
			raise ToolError(f"Invalid or impossible state: {state}")

		value = self.state_values[code]
		if starting_player == 'O':
			value = -value

		return str(value)


@fig.component('ttt/tool/next')
class NextMove(TTT_Tool):
	def __init__(self, **kwargs):
		super().__init__(**kwargs)

		path = repo_root().joinpath('assets', 'ttt', f'minimax.json')
		if not path.exists():
			raise FileNotFoundError(path)
		self.possible_states = json.load(path.open('r'))

	@property
	def name(self) -> str:
		return 'next_moves'

	def description(self) -> str:
		return ('Get all possible next moves for the given tic-tac-toe board state.'
				'Returns an empty list if the game is over.')

	def schema(self, style: str = None) -> JSONOBJ:
		return {
			"type": "function",
			"function": {
				"name": self.name,
				"description": self.description(),
				"parameters": {
					"type": "object",
					"properties": {
						"state": self._representation_schema(),
						"current_player": {
							"type": "string",
							"description": "The current player, either 'X' or 'O'.",
							"enum": ["X", "O"],
						}
					},
					"required": ["state", "current_player"]
				}
			}
		}

	@classmethod
	def check_winner(cls, state: str) -> Optional[str]:
		lines = [
			state[0:3], state[3:6], state[6:9],  # rows
			state[0::3], state[1::3], state[2::3],  # columns
			state[0::4], state[2:7:2]  # diagonals
		]
		for line in lines:
			if line == 'XXX':
				return 'X'
			if line == 'OOO':
				return 'O'
		return None

	@classmethod
	def generate_next_states(cls, state: str):
		"""
		Generate all possible next states from the current state.
		"""
		if cls.check_winner(state) is not None:
			return []
		is_x_turn = state.count('X') == state.count('O')
		next_states = []
		for i in range(9):
			if state[i] == ' ':
				new_state = state[:i] + ('X' if is_x_turn else 'O') + state[i + 1:]
				next_states.append(new_state)
		return next_states

	def call(self, arguments: JSONOBJ, *, seed: Optional[int] = None) -> str:
		assert isinstance(arguments, dict), f'Expected a dict, got {type(arguments)}'
		if 'state' not in arguments:
			raise ToolError("Missing 'state' in arguments")
		if 'current_player' not in arguments:
			raise ToolError("Missing 'current_player' in arguments")
		state = arguments['state']
		current_player = arguments['current_player']
		if current_player not in ['X', 'O']:
			raise ToolError("Invalid current player. Must be 'X' or 'O'.")

		error = self.validate(state)
		if error:
			raise ToolError(error)

		code = self.decode(state)
		starting_player = 'X' if ((code.count('X') == code.count('O') and current_player == 'X')
								  or code.count('X') > code.count('O')) else 'O'

		if starting_player == 'O':
			code = code.replace('X', '_').replace('O', 'X').replace('_', 'O')
		if code not in self.possible_states:
			raise ToolError(f"Invalid or impossible state: {state}")

		next_codes = self.generate_next_states(code)
		if starting_player == 'O':
			next_codes = [state.replace('X', '_').replace('O', 'X').replace('_', 'O') for state in next_codes]

		next_states = [self.encode(state) for state in next_codes]
		return json.dumps(next_states)




