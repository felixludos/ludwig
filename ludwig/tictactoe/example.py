from ..imports import *
from ..core import Task, LLM_Tool, ParsingError



class TakeTheMiddle(Task):
	@property
	def name(self) -> str:
		return "TTT-TakeTheMiddle"

	@property
	def total_questions(self) -> Optional[int]:
		return 1 # for demo purposes

	def context(self) -> str:
		return "Implement all the rules of tic-tac-toe."

	def description(self) -> str:
		return "We're playing tic-tac-toe."

	def load(self, index: int, *, seed: Optional[int] = None) -> Tuple[List[str], bool]:
		# This is a placeholder implementation for demo purposes.
		return ['bottom left', 'top-center', 'middle left', 'top left', 'the remaining bottom corner'], False

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


