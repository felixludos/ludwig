from .imports import *
from .files import Checkpointable



class ToolBase(fig.Configurable, Checkpointable, AbstractTool):
	def json(self) -> JSONOBJ:
		return self.schema()



# class SimpleTool(ToolBase):





