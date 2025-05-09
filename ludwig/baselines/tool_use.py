from .imports import *
from ..abstract import AbstractTool
from ..util import ToolError
from .simple import DirectPrompting


@fig.component('tool-use')
class ToolUse(DirectPrompting):
	"""
	Tool use strategy.
	"""
	def __init__(self, tools: Union[Dict[str, AbstractTool], Iterable[AbstractTool]] = None, max_turns: int = None,
				 **kwargs):
		if tools is None:
			tools = []
		elif isinstance(tools, dict):
			tools = tools.values()
		super().__init__(**kwargs)
		self.tools = {t.name: t for t in tools}
		self._tool_code = hash_str(''.join(sorted(self.tools.keys())))
		self._tool_stats = {}
		self._max_turns = max_turns

	def prepare(self, seed: Optional[int] = None) -> Any:
		super().prepare(seed)
		if not len(self.tools):
			raise ValueError('No tools provided for tool use strategy')

	@property
	def name(self) -> str:
		return f'tool-use-{self.template.ident}-{self._tool_code[:4]}'

	def json(self) -> JSONOBJ:
		return {
			'tool_code': self._tool_code,
			'tools': [tool.json() for tool in self.tools.values()],
			**super().json()
		}

	def status(self) -> Optional[JSONOBJ]:
		status = super().status()
		if status is None:
			return None
		status['tools'] = self._tool_stats
		return status

	def solve(self, question: str, *, side_information: Optional[JSONOBJ] = None) -> Tuple[str, JSONOBJ]:
		prompt = self.template.fill(
			system_context=self.system_context,
			task_context=self.task_context,
			question=question
		)

		tool_calls = []

		tool_schemas = [tool.schema() for tool in self.tools.values()]
		chat = self.client.begin_chat(prompt)
		for resp in self.client.multi_turn(chat, tools=tool_schemas):
			if resp.choices[0].message.tool_calls:
				for tool_call in resp.choices[0].message.tool_calls:
					info = tool_call.function
					assert info.name in self.tools, f'Tool {info.name} not registered'
					tool = self.tools[info.name]
					arguments = json.loads(info.arguments)
					try:
						result = tool.call(arguments)
					except ToolError as e:
						result = str(e) if type(e) == ToolError else f'{e.__class__.__name__}: {e}'
					chat.append({'role': 'tool', 'content': result, 'tool_call_id': tool_call.id, })#'name': info.name})
					tool_calls.append({'name': info.name, 'arguments': arguments, 'result': result})

			elif resp.choices[0].message.content is None:
				raise StrategyFailure('No response from model (and no tool calls)')
			else:
				break

			if self._max_turns is not None and len(chat) >= self._max_turns:
				raise BudgetExceededError(f'Max turns exceeded {self._max_turns} (current: {len(chat)})')

		for call in tool_calls:
			name = call['name']
			if name not in self._tool_stats:
				self._tool_stats[name] = 0
			self._tool_stats[name] += 1

		response = resp.choices[0].message.content

		return response, {'prompt': prompt, 'tool_calls': tool_calls}
