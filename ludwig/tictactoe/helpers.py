from ..imports import *
from ..util import repo_root, AbstractFormalizer
from ..util.prompts import SimpleFormalizer
from tabulate import tabulate

_ttt_data = json.load(repo_root().joinpath('assets', 'ttt', 'minimax.json').open('r'))

def to_nested(board: str) -> List[List[str]]:
	"""
	Convert a string representation of a Tic Tac Toe board into a nested list.
	"""
	board = board
	return [list(board[i:i+3]) for i in range(0, 9, 3)]

def view_ttt(board: str, style: str = 'grid') -> str:
	if style != 'grid':
		board = board.replace(' ', '.')
	nested = [board[i:i+3] for i in range(0, 9, 3)]
	if style == 'minimal':
		return '\n'.join(row for row in nested)
	# elif style == 'compact':
	# 	return '\n---+---+---\n'.join([' ' + ' | '.join(row) + ' ' for row in nested])
	elif style == 'space':
		return '\n'.join([' '.join(row) for row in nested])
	elif style == 'compact':
		return '\n'.join([' ' + ' | '.join(row) + ' ' for row in nested])
	elif style == 'grid':
		return tabulate(nested, tablefmt=style, stralign='center', numalign='center')
	else:
		raise ValueError(f'Invalid style: {style}. Supported styles are: minimal, compact, grid.')

def invert_board(state: str) -> str:
	return state.replace('X', '_').replace('O', 'X').replace('_', 'O')

def is_standardized(state: str, current_player: str = 'X') -> bool:
	return infer_starting_player(state, current_player) == 'X'

def infer_starting_player(state: str, current_player: str = 'X') -> str:
	return 'X' if ((state.count('X') == state.count('O') and current_player == 'X')
								  or state.count('O') < state.count('X')) else 'O'

def infer_current_player(state: str, starting_player: str = 'X') -> str:
	if starting_player == 'O':
		return 'O' if infer_current_player(state) == 'X' else 'X'
	return 'X' if state.count('X') == state.count('O') else 'O'

def validate_state(state: str, starting_player: str = 'X') -> Optional[str]:
	if starting_player == 'O':
		return validate_state(invert_board(state))

	if len(state) != 9:
		return 'Invalid state: incorrect format'

	if not all(c in 'XO ' for c in state):
		return 'Invalid state: must contain only X, O, or space characters.'

	diff = state.count('X') - state.count('O')
	if abs(diff) > 1:
		return 'Invalid state: wrong number of Xs vs Os.'

	current_player = infer_current_player(state)
	if (current_player == starting_player) != (diff == 0):
		return f'Invalid state: wrong number of Xs vs Os for current player {current_player}.'
	if (current_player != starting_player
			and state.count(current_player) > state.count(starting_player)):
		return f'Invalid state: {current_player} cannot be the current player with this state.'

	if state not in _ttt_data:
		return 'Invalid state: game should\'ve ended already.'

	return None


def check_winner(state: str) -> Optional[str]:
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


def generate_next_states(state: str, starting_player: str = 'X') -> Iterator[str]:
	"""
	Generate all possible next states from the current state.
	"""
	if starting_player == 'O':
		yield from map(invert_board, generate_next_states(invert_board(state)))
		return
	elif check_winner(state) is None:
		is_x_turn = state.count('X') == state.count('O')
		for i in range(9):
			if state[i] == ' ':
				new_state = state[:i] + ('X' if is_x_turn else 'O') + state[i + 1:]
				yield new_state


def winning_moves(state: str, player: str = 'X') -> Iterator[int]:
	if check_winner(state):
		return
	for i in range(9):
		if state[i] == ' ':
			new_state = state[:i] + player + state[i + 1:]
			if check_winner(new_state) == player:
				yield i


def best_moves(state: str, starting_player: str = 'X') -> Iterator[int]:
	"""
	Find the best moves for the given player in the current state.
	"""
	if starting_player == 'O':
		yield from best_moves(invert_board(state))
		return

	if state not in _ttt_data:
		raise ValueError(f'Invalid state: {state!r}.')

	current_player = infer_current_player(state)
	candidates = [i for i in range(9) if state[i] == ' ']
	if check_winner(state) is not None or not candidates:
		return

	moves = {}
	for i in candidates:
		new_state = state[:i] + current_player + state[i + 1:]
		if check_winner(new_state) == current_player:
			yield i
		else:
			moves[i] = new_state

	vals = {i: _ttt_data[new_state] for i, new_state in moves.items()}

	best = (max if current_player == 'X' else min)(vals.values())

	for i, val in vals.items():
		if val == best:
			yield i



class TTT_Formalizer(SimpleFormalizer):
	def schema(self) -> JSONOBJ:
		return {'title': 'TicTacToeGameState',
 'description': 'Represents the state of a Tic-Tac-Toe game.',
 'type': 'object',
 'properties': {'board': {'type': 'array',
   'description': 'A 2D array representing the Tic-Tac-Toe board.',
   'items': {'type': 'array',
    'items': {'type': 'string',
     'enum': ['', 'X', 'O'],
     'description': "Represents a cell on the board. ' ' for empty, 'X' for player X, and 'O' for player O."}},
   'minItems': 3,
   'maxItems': 3},
  'currentPlayer': {'type': 'string',
   'enum': ['X', 'O'],
   'description': "Indicates which player's turn it is."},
 'required': ['board', 'currentPlayer']}}

	@staticmethod
	def default_formalize(board, active_player):
		symbols = {' ': ''}
		board = [symbols.get(cell, cell) for cell in board]
		state = {
			'board': [[board[0], board[1], board[2]], [board[3], board[4], board[5]], [board[6], board[7], board[8]]],
			'currentPlayer': active_player,
		}
		return state

	def formalization_args(self, context: JSONOBJ) -> JSONOBJ:
		return {'board': context['problem'], 'active_player': 'O'}



def test_state_validation():
	ttt_data = json.load(repo_root().joinpath('assets', 'ttt', 'minimax.json').open('r'))

	from itertools import product
	for state in (''.join(s) for s in product('XO ', repeat=9)):
		error = validate_state(state, 'X') or validate_state(invert_board(state), 'O')
		if not error and state not in ttt_data:
			assert False, f'Invalid state raised no error: {state!r}'
		if error and state in ttt_data:
			assert False, (f'Valid state raised error: {state!r} '
						   f'({validate_state(state, "X")}) '
						   f'({validate_state(invert_board(state), "O")})')

