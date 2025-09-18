import textwrap

from .imports import *
from ..abstract import DECISION
from ..errors import OptionalMethodNotImplemented, ParsingError
from ..util import PromptTemplate, ClientStats, TimeStats



@fig.component('manual-judge')
class ManualJudge(JudgeBase):
	def __init__(self, line_width: int = 80, **kwargs):
		raise NotImplementedError
		super().__init__(**kwargs)
		self._linewidth = line_width
		self._answer_spec = None

	@property
	def name(self) -> str:
		return f'manual'

	def collect_stats(self, include_start: bool = False, **kwargs) -> TimeStats:
		return TimeStats(include_start=include_start, **kwargs)

	def prepare(self, task_spec: JSONOBJ) -> None:
		super().prepare(task_spec)
		assert 'answer' in task_spec, 'Task specification must contain an answer specification'
		if task_spec['answer'] == 'yes/no':
			self._answer_spec = 'yes/no'
		else:
			raise NotImplementedError(f'Unknown answer type: {task_spec["answer"]}')

	def interpret(self, question: str, response: str) -> Tuple[DECISION, Optional[JSONOBJ]]:
		if self._linewidth is not None:
			question = '\n'.join([textwrap.fill(line, width=self._linewidth) for line in question.split('\n')])
			response = '\n'.join([textwrap.fill(line, width=self._linewidth) for line in response.split('\n')])

		lines = [
			f'\nQuestion: {colorize(question, "green")}',
			f'Response: {colorize(response, "blue")}',
		]

		lines.append(f'Response answer (1="yes", 0="no", ""=None) ')

		result = input('\n\n'.join(lines))
		verdict = None
		if len(result):
			verdict = result.strip().startswith('1')

		decision = 'yes' if verdict else 'no'

		return decision, None



@fig.component('client-judge')
class ClientJudge(JudgeBase):
	def __init__(self, client: AbstractClient, *, template: Union[str, Path], **kwargs):
		raise NotImplementedError
		if not isinstance(template, PromptTemplate):
			template = PromptTemplate(template)
		super().__init__(**kwargs)
		self._client = client
		self._template = template
		self._grammar = None

	@property
	def name(self) -> str:
		return f'{self._client.ident}[{self._template.ident}]'

	def prepare(self, task_spec: JSONOBJ) -> None:
		super().prepare(task_spec)
		if not self._client.ping():
			raise ValueError(f'Judge client {self._client.ident} is not ready to use.')
		self._client.prepare()

		assert 'answer' in task_spec, 'Task specification must contain an answer specification'
		if task_spec['answer'] == 'yes/no':
			self._grammar = 'yes/no/unknown'
		else:
			raise NotImplementedError(f'Unknown answer type: {task_spec["answer"]}')

	def json(self) -> JSONOBJ:
		return {'template': self._template.json(), 'client': self._client.json(), **super().json()}

	def collect_stats(self, include_start: bool = False, **kwargs) -> ClientStats:
		return ClientStats(self._client, include_start=include_start, **kwargs)

	def status(self) -> JSONOBJ:
		return {
			'client': self._client.stats(),
			**super().status(),
		}

	def interpret(self, question: str, response: str) -> Tuple[DECISION, Optional[JSONOBJ]]:

		prompt = self._template.fill(
			question=question,
			response=response
		)

		resp = self._client.send(self._client.wrap_prompt(prompt,
														  dict(temperature=0, max_tokens=5, grammar=self._grammar)))

		verdict = self._client.extract_response(resp)
		words = verdict.strip().lower().split()
		if not len(words) or words[0].lower() not in {'yes', 'no', 'unknown'}:
			self._failures += 1
			return None, {'raw': verdict, 'decision': None}

		decision = words[0].lower()
		self._successes += 1
		if decision == 'unknown':
			return None, None
		return decision, None



@fig.component('format-judge')
class FormatJudge(JudgeBase):
	"""
	Appends a request to answer in a specific format at the end of the task description and then extracts
	the answer from the response with regex.
	"""
	def __init__(self, style: str = 'final-answer', **kwargs):
		super().__init__(**kwargs)
		self._style = style
		self._options = None

	_answer_styles = {
		'final-answer': 'Give your final answer in the form: "FINAL ANSWER: {{{options}}}".',
		'boxed': 'Give your final answer in the form: "\\boxed{{{{options}}}}".',
		'end': 'Make sure to end your response with your final answer, '
			   'responding with only one of the following options: {{{options}}}.',
	}
	_answer_regex = {
		'final-answer': r'(?ix)\b(?:the|my)?\s*final\s+answers?\s*(?:is|are|[:=\-])?\s*\**({options})\**',
		'boxed': r'(?ix)\\boxed\s*\{{\s*({options})\s*}}',
		'end': r'(?ix)\b(?:the|my)?\s*final\s+answers?\s*(?:is|are|[:=\-])?\s*\**({options})\**',
	}

	@property
	def name(self) -> str:
		return f'format-judge-{self._style}'

	@staticmethod
	def _find_last(pattern, text) -> Optional[re.Match]:
		options = re.findall(pattern, text, re.IGNORECASE)
		if not options:
			return None
		return options[-1]

	def prepare(self, task: AbstractTask) -> None:
		super().prepare(task)
		task_spec = task.specification()
		assert 'answer' in task_spec, f'Task specification must contain an answer specification: {task_spec}'
		options = None
		answer_spec = task_spec['answer']
		if isinstance(answer_spec, str):
			if '/' in answer_spec:
				options = answer_spec.split('/')
			elif answer_spec == 'option':
				assert 'options' in task_spec, 'Task specification must contain options for "option" answer type'
				options = task_spec['options']
			else:
				raise NotImplementedError(f'Unknown answer specification: {answer_spec!r}')
		self._options = options

	def format_description(self, task_description: str) -> str:
		options = 'answer' if isinstance(self._options, str) else '/'.join(self._options)
		lines = [task_description, self._answer_styles[self._style].format(options=options)]
		return '\n'.join(lines)

	def format_answer(self, answer: str) -> str:
		if self._style == 'final-answer':
			return f'FINAL ANSWER: {answer}'
		elif self._style == 'boxed':
			return f'\\boxed{{{answer}}}'
		elif self._style == 'end':
			return f'{answer}'
		else:
			raise NotImplementedError(f'Unknown answer style: {self._style}')

	def hint(self, ctx: JSONOBJ) -> None:
		assert 'task' in ctx, f'Context must contain a task description, got {ctx.keys()}'
		ctx['task'] = self.format_description(ctx.get('task'))
		ctx['answer'] = self.format_answer(ctx.get('answer'))

	# _final_answer_regex = r'\bFINAL\s+ANSWER\s*:\s*(yes|no)\b'
	# _final_answer_regex = r'(?ix)\b(?:the|my)?\s*final\s+answers?\s*(?:is|are|[:=\-])?\s*\**(yes|no)\**\b'
	# _final_answer_regex = r'(?ix)\b(?:the|my)?\s*final\s+answers?\s*(?:is|are|[:=\-])?\s*\**({options})\**\b'
	def interpret(self, problem: JSONOBJ, response: JSONOBJ) -> JSONOBJ:
		assert 'final' in response, 'Response must contain a final response to interpret'
		final = response['final']
		if final is None:
			self._failures += 1
			return {'decision': None}
		decision = None

		options = self._options
		if isinstance(options, str):
			options = problem[options]

		pattern = self._answer_regex[self._style].format(options='|'.join(map(re.escape,options)))

		match = self._find_last(pattern, final.strip())
		if match:
			decision = match
			# decision = match.group(1).lower().strip()
			self._successes += 1
		else:
			self._failures += 1

		return {'decision': decision}





