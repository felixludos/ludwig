from ..imports import *
from ..base import TaskBase
from ..util import repo_root

from .helpers import *

import chess

# https://github.com/kagisearch/llm-chess-puzzles/tree/main

@fig.component('chess/puzzle')
class ChessPuzzle(TaskBase):
	_problem_path = repo_root().joinpath('assets', 'chess', 'puzzles.csv')
	_analysis_path = repo_root().joinpath('assets', 'chess', 'analysis.json')
	def __init__(self, *, obs_rep: str = 'fen', options: Optional[int] = None, **kwargs):
		assert obs_rep in ['fen', 'pgn', 'white', 'active', 'unicode', 'minimal', 'border'], \
			f'Invalid observation representation: {obs_rep}'
		assert isinstance(options, int) or options in [None, 'all'], f'Invalid options: {options!r}'
		if obs_rep == 'pgn':
			raise NotImplementedError
		super().__init__(**kwargs)
		self._obs_rep = obs_rep
		self._options = options
		self.data = None
		self.analysis = None

	@property
	def name(self) -> str:
		return "ChessPuzzle"

	def prepare(self, seed: Optional[int] = None) -> Any:
		super().prepare(seed)
		if not self._problem_path.exists():
			raise FileNotFoundError(f"Problem data file not found: {self._problem_path}")
		import pandas as pd
		self.data = pd.read_csv(self._problem_path, header=0)
		self.analysis = json.loads(self._analysis_path.read_text())

	def show_keys(self) -> Iterator[str]:
		yield 'question'
		yield 'system'
		yield 'task'

	def store_keys(self) -> Iterator[str]:
		yield 'problem'
		yield 'question'
		yield 'answer'

	def json(self) -> JSONOBJ:
		return {
			'obs_rep': self._obs_rep,
			'options': self._options,
		}

	@property
	def total_questions(self) -> Optional[int]:
		if self.data is None:
			return None
		return len(self.data)

	@property
	def total_dev_questions(self) -> Optional[int]:
		raise NotImplementedError

	def specification(self) -> JSONOBJ:
		return {'answer': 'word', 'options': 'legal'}

	_system_context = "Implement all the rules of chess to solve some chess problems."
	_task_description = ("Can you solve this chess puzzle? You will be given a board position and you must "
						 "find the best move for the side to move. ")
	def ask(self, index: int) -> JSONOBJ:
		ctx = {}

		# dict of data
		raw = self.data.iloc[index].to_dict()
		ctx['puzzle_id'] = raw['PuzzleId']
		analysis = self.analysis[raw['PuzzleId']]
		board = chess.Board(raw['FEN'])

		moves = raw['Moves'].split()
		assert len(moves) >= 2, f'Not enough moves in puzzle {index}: {moves!r}'
		first_move, answer, *other = moves
		board.push_san(first_move)
		fen = board.fen()

		active_player = 'white' if board.turn == chess.WHITE else 'black'

		template = '{board}\n\n(where uppercase letters are white pieces and lowercase letters are black pieces)'
		if self._obs_rep == 'fen':
			obs = f"FEN: {fen}"
		elif self._obs_rep == 'pgn':
			raise NotImplementedError
		elif self._obs_rep == 'white':
			obs = template.format(board=analysis['white_view'])
		elif self._obs_rep == 'active':
			obs = template.format(board=analysis[f'{active_player}_view'])
		elif self._obs_rep == 'unicode':
			obs = board.unicode(invert_color=True)
		else:
			obs = template.format(board=self._render_board(board))

		question = (f"Given the board position:\n\n{obs}\n\nWhat is the best move for {active_player}? "
						   f"Answer using the SAN format.")

		ctx['fen'] = fen
		ctx['player'] = active_player

		ctx['legal'] = sorted(board.san(move) for move in board.legal_moves)
		hint = None
		if self._options is None:
			pass
		elif self._options == 'all':
			# return all legal moves as options in san format
			options = sorted(board.san(move) for move in board.legal_moves)
			ctx['options'] = options
			options = ', '.join(sorted(options))
			hint = f'Possible moves are (the correct answer is one of these): {options}'
		else:
			assert self._options > 0, f'Invalid number of options: {self._options!r}'

			top = [move['Move'] for move in analysis['moves'][:self._options]]
			ctx['options'] = top
			top = sorted(top)
			options = ', '.join(top)
			hint = f'Some moves to consider are: {options}'

		if hint is not None:
			question = f'{question}\n{hint}'

		ctx['question'] = question
		ctx['answer'] = answer

		ctx['system'] = self._system_context
		ctx['task'] = self._task_description
		return ctx

	def _render_board(self, board: chess.Board) -> str:
		if self._obs_rep == 'minimal':
			return str(board)
		elif self._obs_rep == 'unicode':
			return board.unicode(invert_color=True)
		elif self._obs_rep == 'border':
			return board_to_text(board)
		else:
			raise ValueError(f'Unsupported observation representation: {self._obs_rep!r}')



def test_chess_task():

	task = ChessPuzzle(obs_rep='fen', options=3)
	task.prepare()

	ctx = task.ask(0)

	print(ctx)








