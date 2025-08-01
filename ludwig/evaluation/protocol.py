from .imports import *



@fig.component('default-protocol')
class DefaultProtocol(ProtocolBase):
	def __init__(self, task: AbstractTask, strategy: AbstractStrategy, judge: AbstractJudge = None, *,
				 seed: Optional[int] = random.randint(0, 2**31 - 1),
				 # name: str = '{task.name}_{strategy.name}_{now:%y%m%d-%H%M%S}',
				 name: str = '{task.name}_{strategy.name}_{now.strftime("%y%m%d-%H%M%S")}',
				 include_gt_info: bool = False, **kwargs):
		super().__init__(**kwargs)
		self._name_template = name
		self._name = None
		self._master_seed = seed
		random.seed(seed)
		self._now = datetime.now()
		self._extra_info = {}
		self._include_gt_info = include_gt_info
		self._fail_rate = None
		self._use_generate = None

		self.metrics = None
		self.history = None
		self.scores = None
		self.fails = None

		self._answer_type = None

		self._task = task
		self._judge = judge
		self.strategy = strategy

	@property
	def name(self) -> str:
		return self._name

	@property
	def task(self) -> AbstractTask:
		"""The task used in this protocol"""
		return self._task

	@property
	def judge(self) -> Optional[AbstractJudge]:
		if self._judge is not None:
			return self._judge
		if self.task.is_judge:
			return self.task
		return None


	def prepare(self) -> None:
		self.task.prepare(self._master_seed)
		if self.judge is not None:
			self.judge.prepare(self.task)
		self.strategy.prepare(self.task, judge=self.judge)

		# path = None
		# if self.resume is not None:
		# 	assert root is not None, f'root must be provided to resume'
		# 	path = root.joinpath(self.resume)
		# 	if not path.exists():
		# 		raise FileNotFoundError(f'Checkpoint path does not exist: {path}')
		# 	self._name = self.resume
		#
		# 	log_path = path.joinpath('log.jsonl')
		# 	num_failed = 0
		# 	past_iterations = 0
		# 	if log_path.exists():
		# 		with log_path.open('r') as f:
		# 			for raw in f:
		# 				if len(raw):
		# 					# sample = json.loads(raw)
		# 					# if sample.get('failed'):
		# 					# 	num_failed += 1
		# 					past_iterations += 1
		# 	else:
		# 		past_iterations = None
		#
		# 	self._past_iterations = past_iterations
		# 	self._past_failures = num_failed
		#
		# 	_starting_from = f' (starting from {past_iterations})' if past_iterations is not None else ''
		# 	print(f'Resuming {self.resume}{_starting_from}')
		#
		# 	prev_settings_path = path.joinpath('protocol_settings.json')
		# 	if prev_settings_path.exists():
		# 		prev_settings = flatten(json.load(prev_settings_path.open('r')))
		# 		new_settings = flatten(self.json())
		# 		all_keys = set(prev_settings.keys()) | set(new_settings.keys())
		# 		diffs = [(key, prev_settings.get(key, '[N/A]'), new_settings.get(key, '[N/A]'))
		# 				 for key in all_keys if prev_settings.get(key) != new_settings.get(key)]
		# 		if diffs:
		# 			print(f'Found {len(diffs)} differences:')
		# 			print(tabulate(diffs, headers=['key', 'previous', 'current']))
		#
		# 		prev_idx = 1
		# 		old_path = path.joinpath(f'prev_settings{prev_idx}.json')
		# 		while old_path.exists():
		# 			if prev_idx > 1000:
		# 				raise RuntimeError
		# 			prev_idx += 1
		# 			old_path = path.joinpath(f'prev_settings{prev_idx}.json')
		# 		json.dump(prev_settings, old_path.open('w'))
		#
		# else:
		#
		# 	self._past_iterations = 0
		# 	self._past_failures = 0

		if self.history is None:
			self.history = []
		if self.scores is None:
			self.scores = []
		if self.fails is None:
			self.fails = []

		if self._name is None:
			self._name = pformat(self._name_template, protocol=self, task=self.task, strategy=self.strategy,
								 judge=self.judge, now=self._now, seed=self._master_seed, unique=urandom(16).hex())

		# if root is not None:
		# 	if path is None:
		# 		if self.name is None:
		# 			raise ValueError(f'Protocol must have a name: {self.name}')
		# 		path = root / self.name
		# 		if path.exists() and not overwrite:
		# 			raise RuntimeError(f'Output directory {path} already exists. Use --overwrite to overwrite it.')
		# 		path.mkdir(exist_ok=True)
		#
		# 	with path.joinpath('protocol_settings.json').open('w') as f:
		# 		json.dump(self.json(), f)
		#
		# 	return path


	def remaining_iterations(self, limit: Optional[int] = None) -> range:
		"""(optional) Returns the number of iterations remaining in this protocol"""
		n = self.task.total_questions
		if limit is None:
			if n is None:
				raise RuntimeError('Task has no total_questions and no limit was provided.')
			return range(len(self.history), n)
		past = len(self.history)
		if n is None:
			return range(past, past + limit)
		return range(past, min(past + limit, n))

	def describe(self) -> str:
		tbl = [
			('Protocol', self.name),
			('Task', self.task.name),
			('Strategy', self.strategy.name),
			('Model', self.strategy.model_name),
			('Judge', self.judge.name if self.judge is not None else 'None'),
			('Random seed', self._master_seed),
		]
		return tabulate(tbl)

	def pre_loop(self) -> Optional[JSONOBJ]:
		context = self.task.context()
		base_desc = self.task.description()
		desc = base_desc if self.judge is None else self.judge.format_description(base_desc)
		spec = self.task.specification()

		self._use_generate = self.task.total_questions is None

		artifacts = {}
		with self.strategy.collect_stats() as stats:
			try:
				study = self.strategy.study(context, desc, spec)
			except StrategyFailure as e:
				study = {'error': type(e).__name__, 'error_message': str(e), 'traceback': traceback.format_exc()}

		if study is not None:
			artifacts['study'] = study
		if len(stats):
			artifacts['stats'] = stats

		self._answer_type = spec.get('answer')
		metrics = []
		if isinstance(self._answer_type, list):
			metrics = {key: [] for key in spec['answer']}
		elif self._answer_type == 'yes/no':
			metrics = None
		elif self._answer_type is None:
			metrics = None
		elif self._answer_type == 'option':
			metrics = None
		else:
			raise ValueError(f'Unknown answer type: {spec["answer"]}')

		self.metrics = metrics
		return artifacts

	def step(self, idx: int) -> JSONOBJ:
		log = {}
		proc = {}

		problem = self.task.ask(idx)
		proc.update({key: problem.get(key) for key in self.task.store_keys()})
		try:
			public = {key: problem.get(key) for key in self.task.show_keys()}
		except NotImplementedError:
			public = problem.copy()

		if self.judge is not None:
			self.judge.hint(public)

		failed = False
		with self.strategy.collect_stats() as stats:
			try:
				response = self.strategy.solve(public)
			except StrategyFailure as e:
				# response = str(e) if type(e) == StrategyFailure else f'{e.__class__.__name__}: {e}'
				# steps = {'error': type(e).__name__, 'error_message': str(e), 'traceback': traceback.format_exc()}
				failed = True
				response = {'error': type(e).__name__, 'error_message': str(e), 'traceback': traceback.format_exc()}

		if len(stats):
			log.update(stats)

		judge = self.judge
		if failed or judge is None:
			verdict = None
			judgement = None
		else:
			with judge.collect_stats() as judge_stats:
				judgement = judge.interpret(problem, response)
				if judgement is not None:
					response.update(judgement)
				verdict = judge.judge(problem, response)
			if len(judge_stats):
				log['judge'] = judge_stats

		proc.update(response)

		result = self.task.resolve(problem, response)
		if result is not None:
			proc.update(result)

		score = self._aggregate_verdict(idx, verdict)
		sample = {}
		if len(log):
			sample['log'] = log
		if len(proc):
			sample['table'] = proc
		if self.metrics:
			sample['metrics'] = self.metrics

		self.history.append([idx, failed, score])
		if failed:
			self.fails.append(idx)
		if score is not None:
			self.scores.append(score)
		sample['idx'] = idx
		sample['failed'] = failed
		sample.update(self._default_stats())
		return sample

	def _default_stats(self) -> JSONFLAT:
		stats = {}
		stats['score'] = sum(self.scores) / len(self.scores) if len(self.scores) else None
		stats['correct'] = sum(self.scores) / len(self.history) if len(self.history) else None
		stats['iterations'] = len(self.history)
		stats['fails'] = len(self.fails)
		stats['invalid'] = len(self.history) - len(self.scores)
		return stats

	def _aggregate_verdict(self, idx: int = None, verdict: JSONDATA = None):
		if verdict is None:
			return
		if self._answer_type == 'yes/no' or self._answer_type == 'option':
			return verdict
		elif isinstance(self._answer_type, list):
			for key, val in verdict.items():
				if val is not None:
					self.metrics.setdefault(key, []).append(val)
			return {key: sum(vals) / len(vals) for key, vals in self.metrics.items() if len(vals)}
		elif self._answer_type is None:
			return
		else:
			raise ValueError(f'Unknown answer type: {self._answer_type}')

	def post_loop(self) -> Optional[JSONOBJ]:
		"""Post-loop cleanup or finalization"""
		data = self.status()
		if 'metrics' in data:
			data.update(data['means'])
			del data['metrics'], data['means']
		return data

	def status(self) -> JSONOBJ:
		info = self._default_stats()
		task_status = self.task.status()
		if task_status is not None:
			info['task'] = task_status
		strategy_status = self.strategy.status()
		if strategy_status is not None:
			info['strategy'] = strategy_status
		judge_status = self.judge.status()
		if judge_status is not None:
			info['judge'] = judge_status

		if isinstance(self._answer_type, list):
			info.update({key: sum(vals) / len(vals) for key, vals in self.metrics.items() if len(vals)})
		elif self._answer_type is None:
			pass
		elif self._answer_type == 'yes/no' or self._answer_type == 'option':
			pass
		else:
			raise ValueError(f'Unknown answer type: {self._answer_type}')
		return info

	def summary(self) -> str:
		data = self.status()
		if 'metrics' in data:
			data.update(data['means'])
			del data['metrics'], data['means']
		data = flatten(data)
		if 'accuracy' in data:
			data['accuracy'] = f'{data["accuracy"]:.1%}'
		tbl = list(data.items())
		return tabulate(tbl)

	def remember(self, **info: JSONDATA):
		self._extra_info.update(info)

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
			'model': self.strategy.model_name,
			'judge': judge_json,
			'seed': self._master_seed,
			'entra': self._extra_info,
		**super().json()}

	def checkpoint(self, path: Optional[Path] = None, *, overwrite: bool = True) -> Union[JSONOBJ, Path]:
		if path is None or path.suffix != '':
			return super().checkpoint(path=path, overwrite=overwrite)
		if not path.exists():
			path.mkdir(exist_ok=True)
		elif not overwrite:
			raise FileExistsError(f'checkpoint directory already exists: {path}')
		assert path.is_dir(), f'path must be a directory: {path}'

		task_path = self.task.checkpoint(path.joinpath('task')).relative_to(path)
		strat_path = self.strategy.checkpoint(path.joinpath('strategy')).relative_to(path)

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
		data['status'] = self.status()
		data['state'] = {
			'scores': self.scores,
			'fails': self.fails,
			'history': self.history,
			'metrics': self.metrics,
		}
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
		state = data.get('state', {})
		self.scores = state.get('scores', [])
		self.fails = state.get('fails', [])
		self.history = state.get('history', [])
		self.metrics = state.get('metrics', {})




