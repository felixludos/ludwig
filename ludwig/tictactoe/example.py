from ..abstract import PROBLEM
from ..imports import *
from ..base import TaskBase
from ..util import ToolBase, ToolError, repo_root
from ..errors import ParsingError
import re


@fig.component('ttt/manual-take-the-middle')
class ManualTakeTheMiddle(TaskBase):
	def __init__(self, *, easy: bool = False, **kwargs):
		super().__init__(**kwargs)
		self._easy = easy
	@property
	def name(self) -> str:
		return f"TTT-TakeTheMiddle{'-easy' if self._easy else ''}"

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
		['the top right', 'left bottom', 'top middle', 'upper left', 'the remaining bottom corner'],
		['left bottom corner', 'the right bottom corner', 'left middle', 'top-left', 'the last open corner'],
	]
	_answer_data = ['no', 'yes', 'no', 'yes', ]#'no', 'yes', 'no', 'yes']
	_board_data = [ # X = Alice, O = I
		[['O', 'O', ''], ['X', '', ''], ['X', '', 'X']],
		[['O', 'X', ''], ['X', '', 'X'], ['O', '', '']],
		[['O', 'X', 'X'], ['', '', ''], ['O', '', 'X']],
		[['O', '', 'X'], ['X', '', ''], ['X', '', 'O']],
		# [['X', 'O', ''], ['', '', 'X'], ['X', '', 'O']],
		# [['', 'O', ''], ['X', '', ''], ['X', 'O', 'X']],
		# [['O', 'X', 'O'], ['X', '', ''], ['X', '', '']],
		# [['X', 'O', 'X'], ['', '', 'O'], ['', '', 'X']],
	]

	def load(self, index: int, *, seed: Optional[int] = None) -> Tuple[List[str], str]:
		# This is a placeholder implementation for demo purposes.
		base_idx = index % len(self._problem_data)
		return index, self._answer_data[base_idx]

	def observe(self, problem: List[str], *, seed: int = None) -> str:
		base_idx = problem % len(self._problem_data)
		rev_flags = problem // len(self._problem_data)
		rev_1 = rev_flags % 2
		rev_2 = (rev_flags // 2) % 2

		terms = self._problem_data[base_idx].copy()
		if rev_1:
			terms[0], terms[2] = terms[2], terms[0]
		if rev_2:
			terms[1], terms[3] = terms[3], terms[1]

		# This is a placeholder implementation for demo purposes.
		template = ("Alice started with {0} and I played {1}. She took {2}, so I responded with {3}. "
					"Now Alice played at {4}. I think I should play in the center-middle "
					"because it's a good spot in general. "
					"Is that my best move?")
		template = ("Alice started with {0} and I played {1}. She took {2}, so I responded with {3}. "
					"Now Alice played at {4}. Should I play in the center-middle - is that my best move?")
		if self._easy:
			board = '\n---+---+---\n'.join(' {0} | {1} | {2} '.format(*[x or ' ' for x in row])
										   for row in self._board_data[base_idx])
			template = ("Alice (playing \"X\") started with {0} and I played {1}. She took {2}, so I responded with {3}. "
						"Now Alice played at {4}. "
						f"So the current state is:\n{board}\n\n"
						"Should I play (with \"O\") in the **center-middle** cell - is that my best move?")

		return template.format(*terms)

	def side_information(self, problem: PROBLEM) -> Optional[JSONOBJ]:
		# This is a placeholder implementation for demo purposes.
		index = problem
		base_idx = index % len(self._problem_data)
		return {
			'board': self._board_data[base_idx],
		}


