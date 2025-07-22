from ..imports import *
from tabulate import tabulate

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


