import random

from ..abstract import PROBLEM
from ..imports import *
from ..base import TaskBase
from ..util import ToolBase, ToolError, repo_root
from .helpers import *
from .tools import BestNextMove


@fig.component('ttt/take-the-middle')
class TakeTheMiddle(TaskBase):
	def __init__(self, *, obs_rep: str = 'compact', **kwargs):
		assert obs_rep in ['moves', 'grid', 'compact', 'minimal', 'pythonic'], \
			f'Invalid observation representation: {obs_rep}'
		super().__init__(**kwargs)
		self._obs_rep = obs_rep
		self._problem_path = repo_root().joinpath('assets', 'ttt', 'take-the-middle.json')
		self._action_path = repo_root().joinpath('assets', 'ttt', 'locations.yml')
		self._problem_data = None
		self._dev_order = None
		self._problem_order = None
		self._action_data = None

	@property
	def name(self) -> str:
		return f"TakeTheMiddle"

	def prepare(self, seed: Optional[int] = None) -> Any:
		super().prepare(seed)
		if not self._problem_path.exists():
			raise FileNotFoundError(f"Problem data file not found: {self._problem_path}")
		self._problem_data = json.load(self._problem_path.open('r'))
		self._problem_order = tuple(self._problem_data.keys())
		self._dev_order = self._problem_order[:10]  # First 5 problems for dev set
		self._problem_order = self._problem_order[10:]
		if not self._action_path.exists():
			raise FileNotFoundError(f"Action data file not found: {self._action_path}")
		self._action_data = yaml.safe_load(self._action_path.open('r'))

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
		}

	@property
	def total_questions(self) -> Optional[int]:
		if self._problem_order is None:
			return None
		return len(self._problem_order)

	@property
	def total_dev_questions(self) -> Optional[int]:
		if self._dev_order is None:
			return None
		return len(self._dev_order)

	def ask_dev(self, index: int) -> JSONOBJ:
		return self.ask(index, dev=True)

	def evaluate(self, ctx: JSONOBJ, response: JSONOBJ) -> JSONOBJ:
		pass

	_system_context = "Implement all the rules of tic-tac-toe."
	_task_description = "We're playing tic-tac-toe, and I have a question about the best move to make."
	def ask(self, index: int, dev: bool = False) -> JSONOBJ:
		ctx = {}

		problem = self._problem_order[index]
		answer = self._problem_data[problem]
		ctx['problem'] = problem
		ctx['answer'] = answer


		question = 'Should I play in the central cell - is that my best move?'
		template = 'Alice is "X" and I am "O". Take a careful look at the current situation:\n{board}\n{question}'

		if self._obs_rep == 'moves':
			template = ("Alice started with the {0} and I played the {1}. She took the {2}, so I responded with the {3}. "
						"Now Alice played at the {4}. {question}")

			actions = self._to_action_sequence(problem)
			ctx['actions'] = actions
			prompt = template.format(*actions, question=question)

		elif self._obs_rep in {'grid', 'compact', 'minimal',}:
			board = view_ttt(problem, self._obs_rep)
			prompt = template.format(question=question, board=board)
			# ctx['board'] = board

		elif self._obs_rep == 'pythonic':
			board = str(to_nested(problem))
			prompt = template.format(question=question, board=board)
			# ctx['board'] = board

		else:
			raise ValueError(f'Invalid observation representation: {self._obs_rep}')

		ctx['rationale'] = list(self._rationale(ctx))

		ctx['board'] = view_ttt(problem, 'minimal')

		ctx['question'] = prompt
		ctx['system'] = self._system_context
		ctx['task'] = self._task_description
		return ctx

	def _to_action_sequence(self, board: str, seed: Optional[int] = None) -> List[str]:

		x_inds = [i for i, c in enumerate(board) if c == 'X']
		o_inds = [i for i, c in enumerate(board) if c == 'O']

		rng = random.Random(seed) if seed is not None else random.Random()

		rng.shuffle(x_inds)
		rng.shuffle(o_inds)

		actions = []
		for i in range(3):
			actions.append(self._verbalize_action(x_inds[i], rng))
			if i < 2:  # No need to play O after the last X
				actions.append(self._verbalize_action(o_inds[i], rng))

		return actions

	def _verbalize_action(self, index: int, rng: Optional[random.Random] = None) -> str:
		"""
		Convert an action index to a verbal description.
		"""
		if index < 0 or index >= 9:
			raise ValueError(f"Invalid action index: {index}. Must be between 1 and 9.")
		if rng is None:
			rng = random
		return rng.choice(self._action_data[index])

	def _rationale(self, ctx: JSONOBJ) -> Iterator[str]:

		problem = ctx['problem']
		answer = ctx['answer']

		clean = view_ttt(problem, "compact")

		if self._obs_rep == 'moves':
			actions = ctx['actions']

			x_move = '{i+1}. Alice ("X") played at {action}'
			o_move = '{i+1}. You ("O") played at {action}'

			history = [pformat(o_move if i % 2 else x_move, i=i, action=action) for i, action in enumerate(actions)]
			steps = "\n".join(history)
			yield f'First, let\'s list each of the moves made so far to identify the state of the game:\n{steps}'

			yield f'Therefore the current state of the game is:\n{clean}'

		else:
			yield f'First, let\'s look at the current state of the game:\n{clean}'


		yield f'Next, I need to determine what the best move/s are for you ("O").'

		best = list(best_moves(problem))

		yield (f'The best move{"s" if len(best) > 1 else ""} for you ("O") '
			   f'{"are" if len(best) > 1 else "is"}: {", ".join(self._action_data[i][0] for i in best)}.')

		if 4 in best:
			yield (f'Since the central cell is one of the best moves, you should play there. '
				   f'So the answer to your question is "yes."')
		else:
			yield (f'The central cell is not one of the best moves, so you should not play there. '
				   f'So the answer to your question is "no."')
		#
		# yield (f'Next, I need to determine if the central cell is the best move for me ("O"). '
		# 	   f'I\'ll start by checking for moves that lead to an immediate win.')
		#
		# o_winning_moves = list(winning_moves(problem, 'O'))
		# if len(o_winning_moves):
		# 	yield (f'You have {len(o_winning_moves)} winning move{"s" if len(o_winning_moves) > 1 else ""} available: '
		# 		   f'{", ".join(self._action_data[i][0] for i in o_winning_moves)}.')
		#
		# 	if 4 in o_winning_moves:
		# 		yield (f'Since the central cell is on of the winning moves, you should play there. '
		# 			   f'So the answer to your question is "yes."')
		# 	else:
		# 		yield (f'The central cell is not one of the winning moves, so you should not play there. '
		# 			   f'So the answer to your question is "no."')
		#
		#
		#
		# x_winning_moves = list(winning_moves(problem, 'X'))
		#
		# if len(o_winning_moves):
		# 	pass
		#
		#
		# if answer == 'yes':
		# 	return "Playing in the central cell is the best move because it maximizes my chances of winning."
		# elif answer == 'no':
		# 	return "Playing in the central cell is not the best move because there are better options available."
		# else:
		# 	return "I cannot determine the best move at this time."
		return



	def context(self) -> str:
		return self._system_context

	def description(self) -> str:
		return self._task_description

	def specification(self) -> JSONOBJ:
		return {'answer': 'yes/no'}

	def load(self, index: int, *, seed: Optional[int] = None) -> Tuple[str, str]:
		problem = self._problem_order[index]
		answer = self._problem_data[problem]
		return problem, answer

	def observe(self, problem: str, *, seed: int = None) -> str:

		question = 'Should I play in the central cell - is that my best move?'

		template = 'Alice is "X" and I am "O". Take a careful look at the current situation:\n{board}\n{question}'

		if self._obs_rep == 'moves':
			template = ("Alice started with the {0} and I played the {1}. She took the {2}, so I responded with the {3}. "
						"Now Alice played at the {4}. {question}")
			return template.format(*self._to_action_sequence(problem), question=question)

		elif self._obs_rep == 'grid':
			return template.format(question=question, board=view_ttt(problem, 'grid'))

		elif self._obs_rep == 'compact':
			return template.format(question=question, board=view_ttt(problem, 'compact'))

		elif self._obs_rep == 'minimal':
			return template.format(question=question, board=view_ttt(problem, 'minimal'))

		elif self._obs_rep == 'pythonic':
			return template.format(question=question, board=str(to_nested(problem)))

		else:
			raise ValueError(f'Invalid observation representation: {self._obs_rep}')

	def side_information(self, problem: PROBLEM) -> Optional[JSONOBJ]:
		"""mostly for debugging"""
		return {
			'board': view_ttt(problem, 'minimal'),
		}



def test_take_the_middle():
	"""
	Test the TakeTheMiddle task.
	"""
	print()

	task = TakeTheMiddle(obs_rep='compact')
	task.prepare(seed=42)

	print(task.total_questions)

	ctx = task.ask(0)
	print(ctx)

	ctx2 = task.ask(10)
	print(ctx2)

	dev = task.ask_dev(0)
	print(dev)
	print(task.total_dev_questions)





# # @fig.component('ttt/take-the-middle')
# class TakeTheMiddle(TaskBase):
# 	def __init__(self, *, obs_rep: str = 'compact', **kwargs):
# 		assert obs_rep in ['desc', 'grid', 'compact', 'minimal', 'pythonic'], f'Invalid observation representation: {obs_rep}'
# 		super().__init__(**kwargs)
# 		self._obs_rep = obs_rep
# 		self._problem_path = repo_root().joinpath('assets', 'ttt', 'take-the-middle.json')
# 		self._action_path = repo_root().joinpath('assets', 'ttt', 'locations.yml')
# 		self._problem_data = None
# 		self._dev_order = None
# 		self._problem_order = None
# 		self._action_data = None
#





