from .imports import *
from .files import Checkpointable
import ast, uuid


class ToolBase(fig.Configurable, Checkpointable, AbstractTool):
	def json(self) -> JSONOBJ:
		# return self.schema()
		return {'class': self.__class__.__name__}

