from .imports import *



@fig.component('default-protocol')
class DefaultProtocol(ProtocolBase):
	def __init__(self, strategy: AbstractStrategy, task: AbstractTask, *,
				 seed: Optional[int] = None, name: str = '{task.name}_{strategy.name}_{now:%y%m%d-%H%M%S}',
				 include_gt_info: bool = False, limit: int = None, **kwargs):
		if seed is None: seed = random.randint(0, 2**31 - 1)
		super().__init__(**kwargs)
		self._name_template = name
		self._name = None
		self._master_seed = seed
		random.seed(seed)
		self._sample_seed = seed
		self._now = datetime.now()
		self._limit = limit
		self._include_gt_info = include_gt_info
		self._past_iterations = None
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

		self._past_iterations = 0

		if self._name is None:
			self._name = self._name_template.format(protocol=self, task=self.task, strategy=self.strategy,
													now=self._now, seed=self._master_seed)

	def remaining_iterations(self) -> range:
		"""(optional) Returns the number of iterations remaining in this protocol"""
		if self._limit is None:
			if self.task.total_questions is None:
				raise RuntimeError('Task has no total_questions and no limit was provided.')
			return range(self._past_iterations, self.task.total_questions)
		return range(self._past_iterations, self._limit)

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

		sample = {}
		start_idx = self.strategy.client.past_requests()
		start = time.time()

		solution, steps = self.strategy.solve(question, seed=self._sample_seed, side_information=info)

		sample['time'] = time.time() - start

		sample.update(steps)
		sample.update(self.strategy.client.stats(starting_from=start_idx))

		correct = self.task.correct(solution, answer)

		self.aggregates['correct' if correct else 'incorrect'].append(idx)

		if self._include_gt_info:
			sample['problem'] = problem
			sample['answer'] = answer

		sample['solution'] = solution
		sample['correct'] = correct

		self._past_iterations += 1
		return sample

	def post_loop(self) -> Optional[JSONOBJ]:
		"""Post-loop cleanup or finalization"""
		return self.status()

	def status(self) -> JSONOBJ:
		N_cor = len(self.aggregates['correct'])
		N_inc = len(self.aggregates['incorrect'])
		N = N_cor + N_inc
		acc = N_cor / N if N > 0 else 0
		return {
			'master-seed': self._master_seed,
			'sample-seed': self._sample_seed,
			'past_iterations': self._past_iterations,
			'remaining_iterations': len(self.remaining_iterations()),

			'task': self.task.status(),
			# 'strategy': self.strategy.status(),
			'client': self.strategy.client.stats(),

			'total': N,
			'correct': N_cor,
			'incorrect': N_inc,
			'accuracy': acc,
			# **self.aggregates,
		}

	def summary(self) -> str:
		data = flatten(self.status())
		data['accuracy'] = f'{data["accuracy"]:.1%}'
		tbl = list(data.items())
		return tabulate(tbl)

	def json(self) -> JSONOBJ:
		return {
			'task': self.task.json(),
			'strategy': self.strategy.json(),
			'seed': self._master_seed,
			'limit': self._limit,
		**super().json()}

	def checkpoint(self, path: Optional[Path] = None, *, overwrite: bool = True) -> Union[JSONOBJ, Path]:
		if path is None or path.suffix != '':
			return super().checkpoint(path=path, overwrite=overwrite)
		if not path.exists():
			path.mkdir(exist_ok=True)
		elif not overwrite:
			raise FileExistsError(f'checkpoint directory already exists: {path}')
		assert path.is_dir(), f'path must be a directory: {path}'

		task_path = self.task.checkpoint(path / 'task').relative_to(path)
		strat_path = self.strategy.checkpoint(path / 'strategy').relative_to(path)

		data = self._checkpoint_data(str(task_path), str(strat_path))
		with path.joinpath('protocol.json').open('w') as f:
			json.dump(data, f, indent=2, sort_keys=True)

		summary = self.summary()
		if summary is not None:
			with path.joinpath('summary.txt').open('w') as f:
				f.write(summary)

		status = self.status()
		if status is not None:
			with path.joinpath('status.json').open('w') as f:
				json.dump(status, f, indent=2, sort_keys=True)
		return path

	def _checkpoint_data(self, task: Optional[str] = None, strategy: Optional[str] = None) -> JSONOBJ:
		data = super()._checkpoint_data()
		data['task'] = self.task.checkpoint() if task is None else task
		data['strategy'] = self.strategy.checkpoint() if strategy is None else strategy
		return data

	def load_checkpoint(self, *, path: Path = None, data: Any = None, unsafe: bool = True) -> Optional[Path]:
		if data is not None or not path.is_dir():
			return super().load_checkpoint(path=path, data=data, unsafe=unsafe)

		self.task.load_checkpoint(path=path / 'task')
		self.strategy.load_checkpoint(path=path / 'strategy')

		with path.joinpath('protocol.json').open('r') as f:
			data = json.load(f)
		self._load_checkpoint_data(data, skip_subs=True, unsafe=unsafe)
		return path

	def _load_checkpoint_data(self, data: JSONOBJ, *, skip_subs: bool = False, unsafe: bool = True) -> None:
		super()._load_checkpoint_data(data)
		if not skip_subs:
			if 'task' in data:
				self.task.load_checkpoint(data=data['task'])
			if 'strategy' in data:
				self.strategy.load_checkpoint(data=data['strategy'])




