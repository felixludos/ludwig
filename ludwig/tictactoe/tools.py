from ..imports import *
from ..base import TaskBase
from ..util import ToolBase, ToolError, repo_root
import re
from .helpers import *


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
			if not isinstance(state, str) or len(state) != 9:
				raise ToolError("State must be a string of length 9.")
			if not all(c in 'XO ' for c in state):
				raise ToolError("State can only contain 'X', 'O', or ' '.")
			return state
		elif self.rep_type == 'list':
			if not isinstance(state, list) or len(state) != 9:
				raise ToolError("State must be a list of length 9.")
			if not all(c in ['X', 'O', ' ', ''] for c in state):
				raise ToolError("State can only contain 'X', 'O', or ' '.")
			_fixes = {'': ' '}
			return ''.join(_fixes.get(x,x) for x in state)
		elif self.rep_type == 'nested':
			if isinstance(state, str) and state[0] == '[':
				if "'" in state and not ('"' in state):
					state = state.replace("'", '"')
				try:
					state = json.loads(state)
				except json.JSONDecodeError as e:
					raise ToolError(f"Invalid JSON format: {e}")
			if not isinstance(state, list) or len(state) != 3:
				raise ToolError("State must be a list of 3 lists.")
			for row in state:
				if len(row) != 3:
					raise ToolError("Each row must have exactly 3 elements.")
				if not all(c in ['X', 'O', ' ', ''] for c in row):
					raise ToolError("State can only contain 'X', 'O', or ' '.")
			_fixes = {'': ' '}
			return ''.join(''.join(_fixes.get(x,x) for x in row) for row in state)
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

		code = self.decode(state)
		starting_player = 'X' if ((code.count('X') == code.count('O') and current_player == 'X')
								  or code.count('X') > code.count('O')) else 'O'

		if starting_player == 'O':
			code = code.replace('X', '_').replace('O', 'X').replace('_', 'O')
		if code not in self.possible_states:
			raise ToolError(f"Invalid or impossible state: {state}")

		next_codes = list(generate_next_states(code))
		if starting_player == 'O':
			next_codes = [state.replace('X', '_').replace('O', 'X').replace('_', 'O') for state in next_codes]

		next_states = [self.encode(state) for state in next_codes]
		return json.dumps(next_states)


@fig.component('ttt/tool/best')
class BestNextMove(TTT_Tool):
	def __init__(self, action_rep: str = 'desc', **kwargs):
		assert action_rep in ('board', 'desc'), f'Invalid action representation type: {action_rep}'
		super().__init__(**kwargs)
		self._action_rep = action_rep

		path = repo_root().joinpath('assets', 'ttt', f'minimax.json') # prefers quick wins
		if not path.exists():
			raise FileNotFoundError(path)
		self.possible_states = json.load(path.open('r'))

	@property
	def name(self) -> str:
		return 'best_next_move'

	def description(self) -> str:
		return ('All the best next moves for the given tic-tac-toe board state.'
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

	_action_names = {
		'X        ': 'left cell in the top row',
		' X       ': 'middle cell in the top row',
		'  X      ': 'right cell in the top row',
		'   X     ': 'left cell in the middle row',
		'    X    ': 'middle cell in the middle row',
		'     X   ': 'right cell in the middle row',
		'      X  ': 'left cell in the bottom row',
		'       X ': 'middle cell in the bottom row',
		'        X': 'right cell in the bottom row',

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

		code = self.decode(state)
		cnt = Counter(code)

		starting_player = 'X' if ((code.count('X') == code.count('O') and current_player == 'X')
								  or code.count('O') < code.count('X')) else 'O'
		if starting_player != current_player and cnt.get('X', 0) == cnt.get('O', 0):
			raise ToolError(f"Invalid state: {state} - too many moves for one player")
		if starting_player == current_player and cnt.get('X', 0) != cnt.get('O', 0):
			raise ToolError(f"Invalid state: {state} - too many moves for one player")
		if starting_player == 'O':
			code = code.replace('X', '_').replace('O', 'X').replace('_', 'O')
		if code not in self.possible_states:
			raise ToolError(f"Invalid or impossible state: {state}")

		current = code
		next_codes = generate_next_states(code)

		# use check_winner
		win = [c for c in next_codes if (check_winner(c) == current_player
										 if starting_player == 'X'
										else check_winner(c) == ('O' if current_player == 'X' else 'X'))]

		# w | s | c | out
		# X | X | X | yes
		# X | X | O |
		# X | O | X |
		# X | O | O | yes
		# O | X | X |
		# O | X | O | yes
		# O | O | X | yes
		# O | O | O |

		if win:
			next_codes = win

		else:

			vals = {code: self.possible_states[code] for code in next_codes}
			if len(vals) == 0:
				return json.dumps([])

			best_fn = None
			if starting_player == 'X':
				best_fn = max if current_player == 'X' else min
			else:
				best_fn = min if current_player == 'X' else max
			best = best_fn(vals.values()) # best = (max if current_player == starting_player else min)(vals.values())

			next_codes = [code for code in next_codes if vals[code] == best]

		actions = [''.join(c[i] if c[i] != current[i] else ' ' for i in range(9)) for c in next_codes]
		if self._action_rep == 'desc':
			if 'X' not in actions[0]:
				actions = [c.replace('X', 'O').replace('O', 'X') for c in actions]
			actions = [self._action_names[c] for c in actions]
		elif self._action_rep == 'board':
			if starting_player == 'O':
				actions = [c.replace('X', '_').replace('O', 'X').replace('_', 'O') for c in actions]
			actions = [self.encode(state) for state in actions]
		else:
			raise ValueError(f"Unknown action representation type: {self._action_rep}")
		return json.dumps(actions)


def test_ttt_tools():

	tool = BestNextMove(rep_type='nested')

	args = {
		'current_player': 'X',
		'state': [
			['X', ' ', 'X'],
			['O', ' ', ' '],
			['O', ' ', 'O']
		],
	}
	out = tool.call(args)
	assert out == json.dumps(['top center']), f'Unexpected output: {out}'

	args = {'current_player': 'O', 'state': [['O', 'X', 'X'], [' ', ' ', ' '], ['O', ' ', 'X']]}
	out = tool.call(args)
	assert out == json.dumps(['middle left']), f'Unexpected output: {out}'

	args = {'current_player': 'X', 'state': [['X', ' ', 'X'], ['O', 'O', ' '], [' ', ' ', ' ']]}
	out = tool.call(args)
	assert out == json.dumps(['top center']), f'Unexpected output: {out}'

	args = {'current_player': 'O', 'state': [['O', 'X', 'O'], ['X', 'O', 'X'], [' ', ' ', ' ']]}
	out = tool.call(args)
	assert out == json.dumps(['bottom left', 'bottom right']), f'Unexpected output: {out}'

	args = {'current_player': 'O', 'state': [['O', ' ', 'O'], ['X', 'X', 'X'], [' ', ' ', ' ']]}
	out = tool.call(args)
	assert out == json.dumps([]), f'Unexpected output: {out}'

	args = {'current_player': 'X', 'state': [['O', 'X', 'O'], ['X', 'X', 'O'], ['O', 'O', 'X']]}
	out = tool.call(args)
	assert out == json.dumps([]), f'Unexpected output: {out}'
	print()
	print(out)

