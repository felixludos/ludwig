from .imports import *
from .abstract import AbstractTool, AbstractTask, AbstractStrategy, AbstractProtocol, AbstractJudge, PROBLEM, ANSWER
from .errors import ToolError, OptionalMethodNotImplemented, AmbiguousFormalizationError
from .util import Checkpointable, AbstractClient, AbstractStats, ClientStats, EmptyStats, AbstractFormalizer



class TaskBase(fig.Configurable, Checkpointable, AbstractTask):
	def prepare(self, seed: Optional[int] = None) -> Any:
		pass

	def status(self) -> Optional[JSONOBJ]:
		return None

	def act(self, problem: PROBLEM, action: ANSWER, info: Optional[JSONOBJ] = None) -> Optional[JSONOBJ]:
		"""
		Act on the problem and response. This is a placeholder method and should be overridden in subclasses.
		"""
		pass

	def resolve(self, problem: JSONOBJ, response: JSONOBJ) -> Optional[JSONOBJ]:
		pass

	def json(self) -> JSONOBJ:
		return {}

	def validate_judge(self, judge: 'AbstractJudge') -> bool:
		"""
		Validate the judge for this task. This is a placeholder method and should be overridden in subclasses.
		"""
		return True

	@property
	def is_judge(self):
		return False
	
	def formalizer(self) -> AbstractFormalizer:
		raise NotImplementedError



class JudgedTask(TaskBase, AbstractJudge):
	@property
	def is_judge(self):
		return True
	
	def collect_stats(self) -> AbstractStats:
		return EmptyStats()



class JudgeBase(fig.Configurable, AbstractJudge):
	def prepare(self, task: AbstractTask) -> None:
		self._successes = 0
		self._failures = 0

	def format_description(self, task_description: str) -> str:
		return task_description

	def hint(self, ctx: JSONOBJ) -> None:
		pass

	_ignore_case = True
	def judge(self, problem: JSONOBJ, response: JSONOBJ) -> JSONDATA:
		assert 'answer' in problem, 'Problem must contain an answer'
		assert 'decision' in response or 'final' in response, 'Problem must contain a decision or final answer'

		allowed = problem['answer']
		if isinstance(allowed, str):
			allowed = [allowed]

		sol = response.get('decision', response.get('final', None))
		if self._ignore_case and isinstance(sol, str):
			sol = sol.lower()
		for ans in allowed:
			if self._ignore_case:
				ans = ans.lower()
			if ans == sol:
				return True
		return False

	def json(self) -> JSONOBJ:
		return {}

	def collect_stats(self) -> AbstractStats:
		return EmptyStats()

	def status(self) -> Optional[JSONOBJ]:
		return {
			'failures': self._failures,
			'successes': self._successes,
			'hit_rate': self._successes / (self._successes + self._failures)
							if self._successes + self._failures > 0 else None,
		}



class ClientStrategy(fig.Configurable, Checkpointable, AbstractStrategy):
	_name = None
	def __init__(self, client: AbstractClient, name: str = None, **kwargs):
		super().__init__(**kwargs)
		self._client = client
		self._is_prepared = False
		if name is not None:
			self._name = name

	@property
	def client(self) -> AbstractClient:
		return self._client
	@client.setter
	def client(self, client: AbstractClient):
		self._client = client

	@property
	def model_name(self) -> str:
		return self.client.ident

	def prepare(self, task: AbstractTask, judge: Optional[AbstractJudge] = None) -> Any:
		"""Prepare the strategy for use. This may include setting up any necessary resources or configurations."""
		client = self.client
		if client is not None:
			if not client.ping():
				raise ValueError(f'Client {client.ident} is not ready to use.')
			client.prepare()
		self._is_prepared = True
		
	def json(self):
		return {
			'client': self.client.json(),
		**super().json()}

	def collect_stats(self, include_start: bool = False, **kwargs) -> ClientStats:
		return ClientStats(self.client, include_start=include_start, **kwargs)

	def status(self) -> Optional[JSONOBJ]:
		return {'client': self.client.stats()}



class ProtocolBase(fig.Configurable, Checkpointable, AbstractProtocol):
	def prepare(self, root: Path = None) -> Any:
		pass


