from .imports import *
from .abstract import AbstractTool, AbstractTask, AbstractStrategy, AbstractProtocol
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
		pass
	
	def solve(self, question: str, *, seed: Optional[int] = None,
			  side_information: Optional[JSONOBJ] = None) -> Tuple[str, JSONOBJ]:
		"""
		Top-level function to solve the question using the strategy, returning only the final answer.
		"""
		raise NotImplementedError("The solve method must be implemented in subclasses.")



class ProtocolBase(fig.Configurable, Checkpointable, AbstractProtocol):
	def prepare(self) -> Any:
		pass


