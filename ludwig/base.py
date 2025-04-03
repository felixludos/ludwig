from .imports import *
from .abstract import AbstractTool, AbstractTask, AbstractStrategy, AbstractProtocol
from .errors import ToolError, OptionalMethodNotImplemented, AmbiguousFormalizationError
from .util import Checkpointable


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
	def prepare(self, seed: Optional[int] = None) -> Any:
		pass

	def status(self) -> Optional[JSONOBJ]:
		return None

	def json(self) -> JSONOBJ:
		return {}


class ProtocolBase(fig.Configurable, Checkpointable, AbstractProtocol):
	def prepare(self) -> Any:
		pass


