from .imports import *
from ..abstract import AbstractTool
from ..util import ToolError, parse_pythonic_tool_calls, parse_json_tool_calls
from .simple import ZeroShotPrompting


@fig.component('tool-use')
class ToolUse(ZeroShotPrompting):
	"""
	Tool use strategy.
	"""
	_name = 'tool'
	def __init__(self, tools: Union[Dict[str, AbstractTool], Iterable[AbstractTool]] = None, max_turns: int = None,
				 check_work: Optional[int] = 0,
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
		self._check_work = check_work
		self.judge = None

	def prepare(self, task: 'AbstractTask', judge: 'AbstractJudge' = None, **kwargs):
		super().prepare(task, judge, **kwargs)
		if not len(self.tools):
			raise ValueError('No tools provided for tool use strategy')
		self.judge = judge

	@property
	def name(self) -> str:
		return f'{self._name}-{self.template.ident}-{self._tool_code[:4]}'

	def json(self) -> JSONOBJ:
		return {
			'tool_code': self._tool_code,
			'tools': [tool.json() for tool in self.tools.values()],
			'check_work': self._check_work,
			**super().json()
		}

	def status(self) -> Optional[JSONOBJ]:
		status = super().status()
		if status is None:
			return None
		status['tools'] = self._tool_stats
		return status

	def solve(self, problem: JSONOBJ) -> JSONOBJ:
		tool_schemas = [tool.schema() for tool in self.tools.values()]
		prompt = self.template.fill(
			**problem,
			tool_schemas=tool_schemas,
			json=json,
		)

		tool_calls = []

		checks = self._check_work
		chat = self.client.begin_chat(prompt)
		msg = None
		for resp in self.client.multi_turn(chat, dict(tools=tool_schemas, tool_choice='none')):
			msg = resp['choices'][0]['message']
			if msg.get('tool_calls'):
				for tool_call in msg.get('tool_calls'):
					info = tool_call['function']
					if info['name'] in self.tools:
						tool = self.tools[info['name']]
						arguments = info['arguments']
						while isinstance(arguments, str):
							arguments = json.loads(arguments)
						try:
							result = tool.call(arguments)
						except ToolError as e:
							result = str(e) if type(e) == ToolError else f'{e.__class__.__name__}: {e}'
						chat.append({'role': 'tool', 'content': result, 'tool_call_id': tool_call['id'], })#'name': info.name})
						tool_calls.append({'name': info['name'],
										   'arguments': str(arguments),
										   'result': str(result),
										   })
					else:
						chat.append({'role': 'tool', 'content': f'Error: {info["name"]!r} does not exist',
									 'tool_call_id': tool_call['id'],})


			elif msg['content'] is None:
				raise StrategyFailure('No response from model (and no tool calls)')
			elif checks and self.judge.interpret(problem, {'final': msg['content']}).get('decision') is None:
				checks -= 1
				chat.append({'role': 'user', 'content': 'You have not answered the question yet. If necessary, '
														'continue calling functions or reasoning and then when you have '
														'an answer, provide it precisely in the specified format.'})
			else:
				break

			if self._max_turns is not None and len(chat) >= self._max_turns:
				raise BudgetExceededError(f'Max turns exceeded {self._max_turns} (current: {len(chat)})')

		for call in tool_calls:
			name = call['name']
			if name not in self._tool_stats:
				self._tool_stats[name] = 0
			self._tool_stats[name] += 1

		final = msg['content']
		return {'final': final, 'tool_calls': tool_calls, 'chat': chat}
