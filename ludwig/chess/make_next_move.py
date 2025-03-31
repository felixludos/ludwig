from ..imports import *
from ..core import Task, LLM_Tool, ParsingError
import chess
import pandas as pd



class MakeNextMove(Task):
	def __init__(self):
		super().__init__()
		self.dataset = None
		self.data_len = None
	@property
	def name(self) -> str:
		return "chess-MakeNextMove"

	@property
	def total_questions(self) -> Optional[int]:
		return 1 # for demo purposes

	def context(self) -> str:
		return ("Implement all the rules of Chess. You will be give a board position and who to move. "
				"You have to make next legal move fro the side to move.")

	def description(self) -> str:
		return "We're playing ches we find our selves in the following situation."

	def load(self, index: int, *, seed: Optional[int] = None) -> Tuple[List[str], str]:
		if self.dataset is None:
			import os

			print(os.getcwd())
			csv_file = '../assets/lichess_db_puzzle.csv'
			if not os.path.exists(csv_file):
				print('WARNING: Full database bnot found using truncated version')
				csv_file = '../assets/truncated_lichess_db_puzzle.csv'
			self.dataset = pd.read_csv(csv_file, nrows=index + 5, header=None)
			self.data_len = len(self.dataset)
		csv_line = self.dataset.iloc[(index  + 1)% self.data_len]
		board_state, next_moves = csv_line[1], csv_line[2]
		return [board_state, ], next_moves.split(' ')[0]

	def observe(self, problem: List[str], *, seed: int = None) -> str:
		# This is a placeholder implementation for demo purposes.
		template = "Alice started with {0} and I played {1}. She took {2}, so I defended with {3}. Now Alice played at {4}. I think I should play in the middle because it's a good spot in general. Is that my best move?"
		return template.format(*problem)

	def correct(self, response: str, answer: bool) -> bool:
		# This is a placeholder implementation for demo purposes.
		clean = response.strip().lower()
		if clean.startswith('yes'):
			return answer
		elif clean.startswith('no'):
			return not answer
		raise ParsingError(response, 'Can\'t decide if the answer is "yes" or "no"')

	@staticmethod
	def draw_chessboard(board, ax):
		from matplotlib.patches import Rectangle
		# Draw squares
		colors = ["#F0D9B5", "#B58863"]
		for rank in range(8):
			for file in range(8):
				color = colors[(rank + file) % 2]
				rect = Rectangle((file, rank), 1, 1, facecolor=color)
				ax.add_patch(rect)

		# Draw pieces
		piece_symbols = {
			'P': '♙', 'N': '♘', 'B': '♗', 'R': '♖', 'Q': '♕', 'K': '♔',
			'p': '♟︎', 'n': '♞', 'b': '♝', 'r': '♜', 'q': '♛', 'k': '♚'
		}
		board_fen = board.board_fen().split('/')
		for rank_idx, rank in enumerate(board_fen):
			file_idx = 0
			for char in rank:
				if char.isdigit():
					file_idx += int(char)
				else:
					piece = piece_symbols[char]
					ax.text(file_idx + 0.5, 7.5 - rank_idx, piece, fontsize=32,
							ha='center', va='center')
					file_idx += 1

		# Set limits and formatting
		ax.set_xlim(0, 8)
		ax.set_ylim(0, 8)
		ax.set_xticks(range(8))
		ax.set_yticks(range(8))
		ax.set_xticklabels(['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'])
		ax.set_yticklabels(range(1, 9))
		ax.tick_params(length=0)
		ax.set_aspect('equal')
		ax.axis('off')

	def display(self, fen):
		import matplotlib.pyplot as plt

		board = chess.Board(fen)

		fig, ax = plt.subplots(figsize=(8, 8))
		MakeNextMove.draw_chessboard(board, ax)
		plt.title("Chess Puzzle Position", fontsize=16)
		plt.show()

if __name__ == '__main__':
	# Example usage:
	# csv_example = ("00sHx,q3k1nr/1pp1nQpp/3p4/1P2p3/4P3/B1PP1b2/B5PP/5K2 b k - 0 17,e8d7 a2e6 d7d8 f7f8,1760,80,83,72,"
	# 			   "mate mateIn2 middlegame short,https://lichess.org/yyznGmXs/black#34,Italian_Game "
	# 			   "Italian_Game_Classical_Variation")

	chess_puzzles = MakeNextMove()
	board_state, next_move = chess_puzzles.load(index=0)
	chess_puzzles.display(board_state[0])
