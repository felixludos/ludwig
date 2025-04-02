from .imports import *
from .abstract import AbstractTool, AbstractTask, AbstractStrategy, AbstractProtocol
from .errors import ToolError, OptionalMethodNotImplemented, AmbiguousFormalizationError



class LLM_Tool(fig.Configurable, AbstractTool):
	pass


class Task(fig.Configurable, AbstractTask):
	def prepare(self, seed: Optional[int] = None) -> Any:
		pass

	def json(self) -> JSONOBJ:
		return {}


class Strategy(fig.Configurable, AbstractStrategy):
	def prepare(self, seed: Optional[int] = None) -> Any:
		pass

	def json(self) -> JSONOBJ:
		return {}


class Protocol(fig.Configurable, AbstractProtocol):
	def prepare(self) -> Any:
		pass


