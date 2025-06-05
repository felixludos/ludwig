import textwrap

from .imports import *
from ..abstract import DECISION
from ..errors import OptionalMethodNotImplemented, ParsingError
from ..util import PromptTemplate, ClientStats, TimeStats



@fig.component('manual-judge')
class ManualJudge(JudgeBase):
	def __init__(self, line_width: int = 80, **kwargs):
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

		resp = self._client.send(self._client.wrap_prompt(prompt, temperature=0, max_tokens=5, grammar=self._grammar))

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
	}
	_answer_regex = {
		'final-answer': r'(?ix)\b(?:the|my)?\s*final\s+answers?\s*(?:is|are|[:=\-])?\s*\**({options})\**\b',
		'boxed': r'(?ix)\\boxed\s*\{{\s*({options})\s*}}',
	}

	@property
	def name(self) -> str:
		return f'format-judge-{self._style}'

	def prepare(self, task_spec: JSONOBJ) -> None:
		super().prepare(task_spec)
		if '/' not in task_spec['answer']:
			raise NotImplementedError(f'Unknown answer type: {task_spec["answer"]} (only fixed choices are supported)')
		self._options = task_spec['answer'].split('/')

	def format_description(self, task_description: str) -> str:
		lines = [task_description, self._answer_styles[self._style].format(options='/'.join(self._options))]
		return '\n'.join(lines)

	# _final_answer_regex = r'\bFINAL\s+ANSWER\s*:\s*(yes|no)\b'
	# _final_answer_regex = r'(?ix)\b(?:the|my)?\s*final\s+answers?\s*(?:is|are|[:=\-])?\s*\**(yes|no)\**\b'
	# _final_answer_regex = r'(?ix)\b(?:the|my)?\s*final\s+answers?\s*(?:is|are|[:=\-])?\s*\**({options})\**\b'
	def interpret(self, question: str, response: str) -> Tuple[DECISION, Optional[JSONOBJ]]:
		clean = response.strip().lower()

		pattern = self._answer_regex[self._style].format(options='|'.join(self._options))
		match = re.search(pattern, clean, re.IGNORECASE)
		if match:
			decision = match.group(1).lower().strip()
			self._successes += 1
			return decision, None

		self._failures += 1
		# if clean.startswith('yes'):
		# 	return answer, {'solution': 'yes'}
		# elif clean.startswith('no'):
		# 	return not answer, {'solution': 'no'}
		# return False, {'solution': None}
		# raise ParsingError(response, 'Can\'t decide if the answer is "yes" or "no"')
		return None, None





