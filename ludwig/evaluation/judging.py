from .imports import *
from ..errors import OptionalMethodNotImplemented, ParsingError
from ..util import PromptTemplate, ClientStats



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
			self._grammar = 'yes/no'
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

	def judge(self, response: str, answer: JSONABLE) -> Tuple[bool, JSONOBJ]:

		prompt = self._template.fill(
			response=response,
			answer=answer
		)

		verdict = self._client.get_response(prompt, temperature=0, max_tokens=5, grammar=self._grammar)

		words = verdict.strip().lower().split()
		if not len(words) or words[0].lower() not in {'yes', 'no'}:
			self._failures += 1
			return False, {'raw': verdict, 'decision': None}

		decision = words[0].lower()
		self._successes += 1
		return answer == decision, {'decision': decision}



@fig.component('final-answer-judge')
class FinalAnswerJudge(JudgeBase):
	@property
	def name(self) -> str:
		return 'final-answer-judge'

	def prepare(self, task_spec: JSONOBJ) -> None:
		super().prepare(task_spec)
		assert task_spec['answer'] == 'yes/no', f'Unknown answer type: {task_spec["answer"]}'

	def format_description(self, task_description: str) -> str:
		return f'{task_description}\nGive your final answer in the form "FINAL ANSWER: {{yes/no}}".'

	# _final_answer_regex = r'\bFINAL\s+ANSWER\s*:\s*(yes|no)\b'
	_final_answer_regex = r'(?ix)\b(?:the|my)?\s*final\s+answers?\s*(?:is|are|[:=\-])?\s*\**(yes|no)\**\b'
	def judge(self, response: str, answer: str) -> Tuple[bool, JSONOBJ]:

		clean = response.strip().lower()

		match = re.search(self._final_answer_regex, clean, re.IGNORECASE)
		if match:
			decision = match.group(1).lower().strip()
			self._successes += 1
			return answer == decision, {'decision': decision}

		self._failures += 1
		# if clean.startswith('yes'):
		# 	return answer, {'solution': 'yes'}
		# elif clean.startswith('no'):
		# 	return not answer, {'solution': 'no'}
		# return False, {'solution': None}
		# raise ParsingError(response, 'Can\'t decide if the answer is "yes" or "no"')
		return False, {'decision': None}





