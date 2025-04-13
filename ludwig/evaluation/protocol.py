from .imports import *



@fig.component('default-protocol')
class DefaultProtocol(ProtocolBase):
	def __init__(self, task: AbstractTask, strategy: AbstractStrategy, judge: AbstractJudge = None, *,
				 seed: Optional[int] = None, name: str = '{task.name}_{strategy.name}_{now:%y%m%d-%H%M%S}',
				 include_gt_info: bool = False, limit: int = None, **kwargs):
		if seed == 'sample': seed = random.randint(0, 2**31 - 1)
		super().__init__(**kwargs)
		self._name_template = name
		self._name = None
		self._master_seed = seed
		random.seed(seed)
		# self._sample_seed = seed
		self._now = datetime.now()
		self._limit = limit
		self._include_gt_info = include_gt_info
		self._past_iterations = None
		self._use_generate = None
		self.aggregates = None

		self._task = task
		self.strategy = strategy
		self.judge = judge

	@property
	def name(self) -> str:
		return self._name

	@property
	def task(self) -> AbstractTask:
		"""The task used in this protocol"""
		return self._task

	def prepare(self) -> None:
		self.task.prepare(self._master_seed)
		self.strategy.prepare(self._master_seed)
		self.judge.prepare(self.task.specification())

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
			('Judge', self.judge.name),
			('Random seed', self._master_seed),
		]
		return tabulate(tbl)

	def pre_loop(self) -> Optional[JSONOBJ]:
		context = self.task.context()
		base_desc = self.task.description()
		desc = self.judge.format_description(base_desc)
		spec = self.task.specification()

		self._use_generate = self.task.total_questions is None

		artifacts = {}
		with self.strategy.collect_stats() as stats:
			study = self.strategy.study(context, desc, spec)

		if study is not None:
			artifacts['study'] = study
		if len(stats):
			artifacts['stats'] = stats

		self.aggregates = {
			'correct': [],
			'incorrect': [],
			# 'scores': [],
		}

		return artifacts

	def step(self, idx: int) -> JSONOBJ:
		# self._sample_seed = random.Random(self._sample_seed).randint(0, 2**31 - 1)
		seed = self._master_seed

		problem, answer = self.task.generate(seed) if self._use_generate \
					 else self.task.load(idx, seed=seed)

		info = self.task.side_information(problem)

		question = self.task.observe(problem, seed=seed)

		log = {}
		proc = {}
		if self._include_gt_info:
			proc['problem'] = problem

		with self.strategy.collect_stats() as stats:
			response, steps = self.strategy.solve(question, seed=seed, side_information=info)
		if len(stats):
			log.update(stats)
		proc.update(steps)
		proc['response'] = response

		with self.judge.collect_stats() as judge_stats:
			correct, judgement = self.judge.judge(response, answer)
		if len(judge_stats):
			log['judge'] = judge_stats
		if judgement is not None:
			proc.update(judgement)

		self.aggregates['correct' if correct else 'incorrect'].append(idx)
		proc['answer'] = answer
		proc['correct'] = correct

		sample = {}
		if len(log):
			sample['log'] = log
		if len(proc):
			sample['table'] = proc

		self._past_iterations += 1
		N_cor = len(self.aggregates['correct'])
		N_inc = len(self.aggregates['incorrect'])
		N = N_cor + N_inc
		acc = N_cor / N if N > 0 else 0
		sample['score'] = acc
		return sample

	def post_loop(self) -> Optional[JSONOBJ]:
		"""Post-loop cleanup or finalization"""
		return self.status()

	def status(self) -> JSONOBJ:
		info = {
			'seed': self._master_seed,
			# 'sample-seed': self._sample_seed,
			'past_iterations': self._past_iterations,
			'remaining_iterations': len(self.remaining_iterations()),
		}
		task_status = self.task.status()
		if task_status is not None:
			info['task'] = task_status
		strategy_status = self.strategy.status()
		if strategy_status is not None:
			info['strategy'] = strategy_status
		judge_status = self.judge.status()
		if judge_status is not None:
			info['judge'] = judge_status

		N_cor = len(self.aggregates['correct'])
		N_inc = len(self.aggregates['incorrect'])
		N = N_cor + N_inc
		acc = N_cor / N if N > 0 else 0
		info.update({
			'total': N,
			'correct': N_cor,
			'incorrect': N_inc,
			'accuracy': acc,
		})
		return info

	def summary(self) -> str:
		data = flatten(self.status())
		data['accuracy'] = f'{data["accuracy"]:.1%}'
		tbl = list(data.items())
		return tabulate(tbl)

	def json(self) -> JSONOBJ:
		task_json = self.task.json()
		task_json['name'] = self.task.name
		strategy_json = self.strategy.json()
		strategy_json['name'] = self.strategy.name
		judge_json = self.judge.json()
		judge_json['name'] = self.judge.name
		return {
			'task': task_json,
			'strategy': strategy_json,
			'client': self.strategy.client.json(),
			'judge': judge_json,
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




