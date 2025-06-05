from .imports import *
from .abstract import AbstractTool, AbstractTask, AbstractStrategy, AbstractProtocol, AbstractJudge, PROBLEM, ANSWER
from .errors import ToolError, OptionalMethodNotImplemented, AmbiguousFormalizationError
from .util import Checkpointable, AbstractClient, AbstractStats, ClientStats, EmptyStats



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

	def judge(self, decision: JSONDATA, answer: JSONDATA, info: Optional[JSONOBJ] = None) -> JSONDATA:
		return decision == answer

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
	def __init__(self, client: AbstractClient, **kwargs):
		super().__init__(**kwargs)
		self._client = client
		self._is_prepared = False

	@property
	def client(self) -> AbstractClient:
		return self._client
	@client.setter
	def client(self, client: AbstractClient):
		self._client = client

	@property
	def model_name(self) -> str:
		return self.client.ident

	def prepare(self, seed: Optional[int] = None) -> Any:
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


