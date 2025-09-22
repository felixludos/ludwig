from .imports import *
from .. import AbstractTask
from ..abstract import AbstractJudge
from ..errors import StrategyFailure


@fig.component('zero-shot')
class ZeroShotPrompting(ClientStrategy):
	_name = 'zshot'
	_default_template = '{task}\n\n{question}'
	def __init__(self, template: Union[PromptTemplate, str] = None,
				 params: Optional[JSONOBJ] = None, **kwargs):
		if template is None:
			template = PromptTemplate(self._default_template, ident='default')
		if not isinstance(template, PromptTemplate):
			template = PromptTemplate(template)
		if params is None:
			params = {}
		super().__init__(**kwargs)
		self.template = template
		self.params = params
		self.system_context = None
		self.task_context = None


	@property
	def name(self) -> str:
		return f'{self._name}-{self.template.ident}'


	def json(self) -> JSONOBJ:
		return {'template': self.template.json(), **super().json()}


	# def study(self, context: str, desc: str, spec: JSONOBJ) -> Optional[JSONDATA]:
	# 	self.system_context = context
	# 	self.task_context = desc


	def prepare(self, task: AbstractTask, judge: Optional[AbstractJudge] = None) -> Any:
		super().prepare(task, judge)
		spec = task.specification()
		if 'schema' in spec:
			self.params['grammar'] = spec['schema']

	def solve(self, problem: JSONOBJ) -> JSONOBJ:
		# assert 'question' in problem, 'Problem must contain a question'
		# question = problem['question']
		for key in self.template.variables():
			if key not in problem:
				print(f'WARNING: Template expects a "{key}" not found in problem. Error is probably imminent.')

		prompt = self.template.fill(**problem)

		# response = self.client.get_response(prompt, **self.params)
		resp = self.client.step(prompt, **self.params)

		response = self.client.extract_response(resp)

		return {'prompt': prompt, 'final': response}


@fig.modifier('mv')
class MajorityVote(ClientStrategy):
	def __init__(self, n_votes: int = 5, **kwargs):
		assert n_votes > 1, 'n_votes must be greater than 1'
		super().__init__(**kwargs)
		self.n_votes = n_votes
		self._judge = None

	def name(self) -> str:
		return f'mv{self.n_votes}-{super().name}'

	def json(self) -> JSONOBJ:
		return {
			'n_votes': self.n_votes,
			**super().json()
		}

	def prepare(self, task: AbstractTask, judge: Optional[AbstractJudge] = None) -> Any:
		if judge is None:
			raise ValueError('MajorityVote strategy requires a judge to be prepared')
		super().prepare(task, judge)
		self._judge = judge

	def collect_votes(self, problem: JSONOBJ) -> List[JSONOBJ]:
		"""
		Collect votes from the client for the given problem.
		This method should be overridden by subclasses to implement specific voting logic.
		"""
		master_seed = self.client.seed
		rng = random.Random(master_seed)
		responses = []
		for i in range(self.n_votes):
			self.client.seed = rng.randint(0, 2**32 - 1)
			response = super().solve(problem)
			responses.append(response)
		self.client.seed = master_seed

		votes = []
		with self._judge.collect_stats() as judge_stats:
			for response in responses:
				vote = self._judge.interpret(problem, response)
				votes.append({**response, **vote})

		return {'votes': votes, 'judge_stats': judge_stats}

	def aggregate(self, problem: JSONOBJ, votes: List[JSONOBJ]) -> JSONOBJ:

		tally = Counter(vote['decision'] for vote in votes['votes'] if 'decision' in vote)
		tally = dict(tally.most_common()[::-1])

		if len(tally) == 0:
			raise StrategyFailure('No valid votes collected')

		votes['failed_votes'] = self.n_votes - sum(tally.values())

		best = max(tally.values())
		decisions = [k for k, v in tally.items() if v == best]
		if len(decisions) == 1:
			final = self._judge.format_answer(decisions[0])
		else:
			raise StrategyFailure(f'Tie in votes: {tally}')

		votes['tally'] = tally
		votes['final'] = final
		return votes

	def solve(self, problem: JSONOBJ) -> JSONOBJ:
		votes = self.collect_votes(problem)
		result = self.aggregate(problem, votes)
		return result


@fig.component('majority-vote')
class SimpleMajorityVote(MajorityVote, ZeroShotPrompting):

	@property
	def name(self) -> str:
		name = f'mv{self.n_votes}-{self._name}' if self._name else f'mv{self.n_votes}'
		return name


@fig.component('few-shot')
class FewShotPrompting(ClientStrategy):
	"""
	Few-shot prompting strategy.
	"""

	_default_intro_template = '{task}\n\n{question}'
	def __init__(self, intro_template: Union[PromptTemplate, str] = None,
				 question_template: Union[PromptTemplate, str] = '{question}',
				 answer_template: Union[PromptTemplate, str] = '{answer}',
				 *, n_shot: int = 5, as_chat: bool = True, params: Optional[JSONOBJ] = None, **kwargs):
		if intro_template is None:
			intro_template = PromptTemplate(self._default_intro_template, ident='default')
		elif not isinstance(intro_template, PromptTemplate):
			intro_template = PromptTemplate(intro_template)
		if not isinstance(question_template, PromptTemplate):
			question_template = PromptTemplate(question_template)
		if not isinstance(answer_template, PromptTemplate):
			answer_template = PromptTemplate(answer_template)
		if params is None:
			params = {}
		assert n_shot > 0, 'n_shot must be a positive integer'
		super().__init__(**kwargs)
		self.intro_template = intro_template
		self.params = params
		self.question_template = question_template
		self.answer_template = answer_template
		self.n_shot = n_shot
		self._as_chat = as_chat
		self._shots = None

	@property
	def name(self):
		name = f'fs{"-nc" if not self._as_chat else ""}' if self._name is None else self._name
		return f'{name}{self.n_shot}-{self.intro_template.ident}'

	def json(self) -> JSONOBJ:
		return {
			'intro_template': self.intro_template.json(),
			'question_template': self.question_template.json(),
			'answer_template': self.answer_template.json(),
			'n_shot': self.n_shot,
			'as_chat': self._as_chat,
			'shots': self._shots,
			**super().json()
		}

	def prepare(self, task: 'AbstractTask', judge: 'AbstractJudge' = None, **kwargs):
		super().prepare(task, judge, **kwargs)

		if self._shots is None:
			shots = []
			assert task.total_dev_questions >= self.n_shot, \
				f'Task must have at least {self.n_shot} dev questions to use {self.name}'
			for i in range(self.n_shot):
				shot = task.ask_dev(i)

				if 'rationale' in shot:
					steps = [line.replace('\n', '\n\t') for line in shot['rationale']]
					shot['rationale'] = '\n'.join(f'{i + 1}. {line}' for i, line in enumerate(steps))

				if judge is not None:
					judge.hint(shot)
				shots.append(shot)
			self._shots = shots


	def solve(self, problem: JSONOBJ) -> JSONOBJ:

		if 'rationale' in problem:
			steps = [line.replace('\n', '\n\t') for line in problem['rationale']]
			problem['rationale'] = '\n'.join(f'{i+1}. {line}' for i, line in enumerate(steps))

		first, *shots = self._shots
		chat = [{'role': 'user', 'content': self.intro_template.fill(**first)},
				{'role': 'assistant', 'content': self.answer_template.fill(**first)},]
		for shot in shots:
			chat.append({'role': 'user', 'content': self.question_template.fill(**shot)})
			chat.append({'role': 'assistant', 'content': self.answer_template.fill(**shot)})

		chat.append({'role': 'user', 'content': self.question_template.fill(**problem)})

		if self._as_chat:
			chat = [*self.client.begin_chat(), *chat]

			response = self.client.get_response(chat, **self.params)

			return {'chat': chat, 'final': response}

		else:
			prompt = '\n\n'.join(message['content'] for message in chat)

			response = self.client.get_response(prompt, **self.params)

			return {'prompt': prompt, 'final': response}


