from ..imports import *
from ..base import TaskBase, ToolBase
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
		return ("We're playing tic-tac-toe, and I have some questions. "
				"Give your final answer in the form \"FINAL ANSWER: {yes/no}\".")

	def specification(self) -> JSONOBJ:
		return {'answer': 'Yes/No'}

	_problem_data = [
		['bottom left', 'top-center', 'middle left', 'top left', 'the remaining bottom corner'],
		['top-center', 'bottom left', 'middle left', 'top left', 'on the right in the middle'],
		['the top right', 'left bottom', 'top middle', 'top left', 'the remaining bottom corner'],
		['left bottom corner', 'the right bottom corner', 'left middle', 'top-left', 'the last open corner'],
	]
	_answer_data = [False, True, False, True]

	def load(self, index: int, *, seed: Optional[int] = None) -> Tuple[List[str], bool]:
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
					"Now Alice played at {4}. I think I should play in the middle because it's a good spot in general. "
					"Is that my best move?")
		return template.format(*problem)

	def correct(self, response: str, answer: bool) -> bool:
		# This is a placeholder implementation for demo purposes.
		clean = response.strip().lower()

		# find "

		match = re.search(r'\bFINAL\s+ANSWER\s*:\s*(yes|no)\b', clean, re.IGNORECASE)
		if match:
			final_answer = match.group(1).lower()

			if final_answer == 'yes':
				return answer
			elif final_answer == 'no':
				return not answer

		if clean.startswith('yes'):
			return answer
		elif clean.startswith('no'):
			return not answer
		return False
		raise ParsingError(response, 'Can\'t decide if the answer is "yes" or "no"')


