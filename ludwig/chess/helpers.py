from ..imports import *

import chess

def board_to_text(board):
	"""
	Creates a text representation of the board with file and rank labels,
	using simple letters for pieces.
	"""
	s = "   a b c d e f g h\n"
	s += " +-----------------+\n"
	for rank in range(7, -1, -1):
		s += f"{rank + 1}|"
		for file in range(8):
			square = chess.square(file, rank)
			piece = board.piece_at(square)

			# The key is piece.symbol() which returns 'P', 'n', 'K', etc.
			symbol = piece.symbol() if piece else "."
			s += f" {symbol}"
		s += f" |{rank + 1}\n"
	s += " +-----------------+\n"
	s += "   a b c d e f g h\n"
	return s



