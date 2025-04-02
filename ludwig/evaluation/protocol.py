from .imports import *


@fig.component('default-protocol')
class DefaultProtocol(Protocol):
	def __init__(self, strategy: AbstractStrategy, task: AbstractTask, *,
				 seed: Optional[int] = None, name: str = '{task.name}_{strategy.name}_{now:%y%m%d-%H%M%S}',
				 limit: int = None, **kwargs):
		if seed is None: seed = random.randint(0, 2**31 - 1)
		super().__init__(**kwargs)
		self._name_template = name
		self._name = None
		self._master_seed = seed
		random.seed(seed)
		self._sample_seed = seed
		self._now = datetime.now()
		self._limit = limit
		self._use_generate = None
		self.aggregates = None

		self.strategy = strategy
		self.task = task


	@property
	def name(self) -> str:
		return self._name


	def prepare(self) -> None:
		self.task.prepare(self._master_seed)
		self.strategy.prepare(self._master_seed)

		if self._name is None:
			self._name = self._name_template.format(protocol=self, task=self.task, strategy=self.strategy,
													now=self._now, seed=self._master_seed)

	def remaining_iterations(self) -> range:
		"""(optional) Returns the number of iterations remaining in this protocol"""
		if self._limit is None:
			if self.task.total_questions is None:
				raise RuntimeError('Task has no total_questions and no limit was provided.')
			return range(self.task.total_questions)
		return range(self._limit)


	def describe(self) -> str:
		tbl = [
			('Protocol', self.name),
			('Task', self.task.name),
			('Strategy', self.strategy.name),
			('Random seed', self._master_seed),
		]
		return tabulate(tbl)


	def pre_loop(self) -> Optional[JSONOBJ]:
		context = self.task.context()
		desc = self.task.description()
		spec = self.task.specification()

		self._use_generate = self.task.total_questions is None

		artifacts = self.strategy.study(context, desc, spec)

		self.aggregates = {
			'correct': [],
			'incorrect': [],
			# 'scores': [],
		}

		return artifacts


	def step(self, idx: int) -> JSONOBJ:
		self._sample_seed = random.Random(self._sample_seed).randint(0, 2**31 - 1)

		problem, answer = self.task.generate(self._sample_seed) if self._use_generate \
					 else self.task.load(idx, seed=self._sample_seed)

		info = self.task.side_information(problem)

		question = self.task.observe(problem, seed=self._sample_seed)

		response = self.strategy.solve(question, seed=self._sample_seed, side_information=info)

		correct = self.task.correct(response, answer)

		self.aggregates['correct' if correct else 'incorrect'].append(idx)

		return {
			'seed': self._sample_seed,
			'problem': problem,
			'info': info,
			'question': question,
			'response': response,
			'answer': answer,
			'correct': correct,
		}


	def post_loop(self) -> Optional[JSONOBJ]:
		"""Post-loop cleanup or finalization"""
		N_cor = len(self.aggregates['correct'])
		N_inc = len(self.aggregates['incorrect'])
		N = N_cor + N_inc
		acc = N_cor / N if N > 0 else 0
		return {
			'total': N,
			'correct': N_cor,
			'incorrect': N_inc,
			'accuracy': acc,
		}


	def summary(self) -> str:
		N_cor = len(self.aggregates['correct'])
		N_inc = len(self.aggregates['incorrect'])
		N = N_cor + N_inc
		acc = N_cor / N if N > 0 else 0
		tbl = [
			('Correct', f'{N_cor}'),
			('Incorrect', f'{N_inc}'),
			('Total', f'{N}'),
			('Accuracy', f'{acc:.1%}'),
		]
		return tabulate(tbl)


	def json(self) -> JSONOBJ:
		return {
			'task': self.task.json(),
			'strategy': self.strategy.json(),
			'seed': self._master_seed,
			'limit': self._limit,
		**super().json()}



