from .imports import *
from .abstract import AbstractTool, AbstractTask, AbstractStrategy, AbstractProtocol, AbstractJudge
from .errors import ToolError, OptionalMethodNotImplemented, AmbiguousFormalizationError
from .util import Checkpointable, AbstractClient


class ToolBase(fig.Configurable, Checkpointable, AbstractTool):
	pass


class TaskBase(fig.Configurable, Checkpointable, AbstractTask):
	def prepare(self, seed: Optional[int] = None) -> Any:
		pass

	def status(self) -> Optional[JSONOBJ]:
		return None

	def json(self) -> JSONOBJ:
		return {}

	def validate_judge(self, judge: 'AbstractJudge') -> bool:
		"""
		Validate the judge for this task. This is a placeholder method and should be overridden in subclasses.
		"""
		return True



class JudgeBase(fig.Configurable, AbstractJudge):
	def prepare(self, task_spec: JSONOBJ) -> None:
		self._successes = 0
		self._failures = 0

	def format_description(self, task_description: str) -> str:
		return task_description

	def json(self) -> JSONOBJ:
		return {}

	def status(self) -> Optional[JSONOBJ]:
		return {
			'failures': self._failures,
			'successes': self._successes,
			'hit_rate': self._successes / (self._successes + self._failures)
							if self._successes + self._failures > 0 else None,
		}


class StrategyBase(fig.Configurable, Checkpointable, AbstractStrategy):
	def __init__(self, client: AbstractClient, **kwargs):
		super().__init__(**kwargs)
		self._client = client

	@property
	def client(self) -> AbstractClient:
		return self._client

	def prepare(self, seed: Optional[int] = None) -> Any:
		"""Prepare the strategy for use. This may include setting up any necessary resources or configurations."""
		if not self.client.ping():
			raise ValueError(f'Client {self.client.ident} is not ready to use.')
		self.client.prepare()

	def json(self):
		return {
			'client': self.client.json(),
		**super().json()}

	def status(self) -> Optional[JSONOBJ]:
		return {'client': self.client.stats()}
	
	def solve(self, question: str, *, seed: Optional[int] = None,
			  side_information: Optional[JSONOBJ] = None) -> Tuple[str, JSONOBJ]:
		"""
		Top-level function to solve the question using the strategy, returning only the final answer.
		"""
		starting_idx = self.client.past_requests()
		start = time.time()

		response, steps = self._solve(question, seed=seed, side_information=side_information)

		end = time.time()
		steps['stats'] = {
			'time': end - start,
			**self.client.stats(starting_from=starting_idx),
		}
		return response, steps

	def _solve(self, question: str, *, seed: Optional[int] = None,
			   side_information: Optional[JSONOBJ] = None) -> Tuple[str, JSONOBJ]:
		raise NotImplementedError("The solve method must be implemented in subclasses.")



class ProtocolBase(fig.Configurable, Checkpointable, AbstractProtocol):
	def prepare(self) -> Any:
		pass


