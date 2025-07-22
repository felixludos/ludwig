from ..abstract import PROBLEM
from ..imports import *
from ..base import TaskBase
from ..util import ToolBase, ToolError, repo_root
from .helpers import *


@fig.component('ttt/take-the-middle')
class TakeTheMiddle(TaskBase):
	def __init__(self, *, obs_rep: str = 'compact', **kwargs):
		assert obs_rep in ['desc', 'grid', 'compact', 'minimal', 'pythonic'], f'Invalid observation representation: {obs_rep}'
		super().__init__(**kwargs)
		self._obs_rep = obs_rep
		self._problem_path = repo_root().joinpath('assets', 'ttt', 'take-the-middle.json')
		self._action_path = repo_root().joinpath('assets', 'ttt', 'locations.yml')
		self._problem_data = None
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
		if not self._action_path.exists():
			raise FileNotFoundError(f"Action data file not found: {self._action_path}")
		self._action_data = yaml.safe_load(self._action_path.open('r'))

	def json(self) -> JSONOBJ:
		return {
			'obs_rep': self._obs_rep,
		}

	@property
	def total_questions(self) -> Optional[int]:
		if self._problem_data is not None:
			return len(self._problem_data)

	def context(self) -> str:
		return "Implement all the rules of tic-tac-toe."

	def description(self) -> str:
		return "We're playing tic-tac-toe, and I have a question about the best move to make."

	def specification(self) -> JSONOBJ:
		return {'answer': 'yes/no'}

	def load(self, index: int, *, seed: Optional[int] = None) -> Tuple[str, str]:
		problem = self._problem_order[index]
		answer = self._problem_data[problem]
		return problem, answer

	def observe(self, problem: str, *, seed: int = None) -> str:

		question = 'Should I play in the central cell - is that my best move?'

		template = 'Alice is "X" and I am "O". Take a careful look at the current situation:\n{board}\n{question}'

		if self._obs_rep == 'desc':
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


	def _to_action_sequence(self, board: str, seed: Optional[int] = None) -> List[str]:

		x_inds = [i for i, c in enumerate(board) if c == 'X']
		o_inds = [i for i, c in enumerate(board) if c == 'O']

		rng = random.Random(seed) if seed is not None else random.Random()

		rng.shuffle(x_inds)
		rng.shuffle(o_inds)

		actions = []
		for i in range(3):
			actions.append(rng.choice(self._action_data[x_inds[i]+1]))
			if i < 2:  # No need to play O after the last X
				actions.append(rng.choice(self._action_data[o_inds[i]+1]))

		return actions











