from .imports import *
from .files import Checkpointable
import ast, uuid
# from openai.types.chat.chat_completion_message_tool_call import ChatCompletionMessageToolCall as ToolCall
# from openai.types.chat.chat_completion_message_tool_call import Function


class ToolBase(fig.Configurable, Checkpointable, AbstractTool):
	def json(self) -> JSONOBJ:
		return self.schema()

