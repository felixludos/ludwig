from .imports import *



@fig.component('default-protocol')
class DefaultProtocol(ProtocolBase):
	def __init__(self, task: AbstractTask, strategy: AbstractStrategy, judge: AbstractJudge = None, *,
				 seed: Optional[int] = None, resume: str = None,
				 # name: str = '{task.name}_{strategy.name}_{now:%y%m%d-%H%M%S}',
				 name: str = '{task.name}_{strategy.name}_{now.strftime("%y%m%d-%H%M%S")}',
				 include_gt_info: bool = False, limit: int = None, **kwargs):
		if seed == 'sample': seed = random.randint(0, 2**31 - 1)
		super().__init__(**kwargs)
		self._name_template = name
		self.resume = resume
		self._name = None
		self._master_seed = seed
		random.seed(seed)
		self._sample_seed = seed
		self._now = datetime.now()
		self._limit = limit
		self._include_gt_info = include_gt_info
		self._past_iterations = None
		self._past_failures = None
		self._fail_rate = None
		self._use_generate = None
		self.metrics = None
		self._answer_type = None

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

	def prepare(self, root: Path = None, overwrite: bool = False) -> None:
		self.task.prepare(self._master_seed)
		self.strategy.prepare(self._master_seed)
		if self.judge is not None:
			self.judge.prepare(self.task.specification())

		path = None
		if self.resume is not None:
			assert root is not None, f'root must be provided to resume'
			path = root.joinpath(self.resume)
			if not path.exists():
				raise FileNotFoundError(f'Checkpoint path does not exist: {path}')
			self._name = self.resume

			log_path = path.joinpath('log.jsonl')
			num_failed = 0
			past_iterations = 0
			if log_path.exists():
				with log_path.open('r') as f:
					for raw in f:
						if len(raw):
							sample = json.loads(raw)
							if sample.get('failed'):
								num_failed += 1
							past_iterations += 1
			else:
				past_iterations = None

			self._past_iterations = past_iterations
			self._past_failures = num_failed

			_starting_from = f' (starting from {past_iterations})' if past_iterations is not None else ''
			print(f'Resuming {self.resume}{_starting_from}')

			prev_settings_path = path.joinpath('protocol_settings.json')
			if prev_settings_path.exists():
				prev_settings = flatten(json.load(prev_settings_path.open('r')))
				new_settings = flatten(self.json())
				all_keys = set(prev_settings.keys()) | set(new_settings.keys())
				diffs = [(key, prev_settings.get(key, '[N/A]'), new_settings.get(key, '[N/A]'))
						 for key in all_keys if prev_settings.get(key) != new_settings.get(key)]
				if diffs:
					print(f'Found {len(diffs)} differences:')
					print(tabulate(diffs, headers=['key', 'previous', 'current']))

				prev_idx = 1
				old_path = path.joinpath(f'prev_settings{prev_idx}.json')
				while old_path.exists():
					if prev_idx > 1000:
						raise RuntimeError
					prev_idx += 1
					old_path = path.joinpath(f'prev_settings{prev_idx}.json')
				json.dump(prev_settings, old_path.open('w'))

		else:

			self._past_iterations = 0
			self._past_failures = 0

		if self._name is None:
			# self._name = self._name_template.format(protocol=self, task=self.task, strategy=self.strategy,
			# 										judge=self.judge, now=self._now, seed=self._master_seed)
			# get random bytes from os
			self._name = pformat(self._name_template, protocol=self, task=self.task, strategy=self.strategy,
								 judge=self.judge, now=self._now, seed=self._master_seed,
													 unique=urandom(16).hex())

		if root is not None:
			if path is None:
				if self.name is None:
					raise ValueError(f'Protocol must have a name: {self.name}')
				path = root / self.name
				if path.exists() and not overwrite:
					raise RuntimeError(f'Output directory {path} already exists. Use --overwrite to overwrite it.')
				path.mkdir(exist_ok=True)

			with path.joinpath('protocol_settings.json').open('w') as f:
				json.dump(self.json(), f)

			return path


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
		if self._answer_type == 'yes/no':
			metrics = {'correct': [], 'incorrect': []}
		elif isinstance(self._answer_type, list):
			metrics = {key: [] for key in spec['answer']}
		elif self._answer_type is None:
			metrics = None
		else:
			raise ValueError(f'Unknown answer type: {spec["answer"]}')

		self.metrics = metrics
		return artifacts

	def step(self, idx: int) -> JSONOBJ:
		log = {}
		proc = {}
		if self._use_generate:
			self._sample_seed = random.Random(self._sample_seed).randint(0, 2**31 - 1)
			problem, answer = self.task.generate(self._sample_seed)
			proc['sample_seed'] = self._sample_seed
		else:
			problem, answer = self.task.load(idx, seed=self._master_seed)

		info = self.task.side_information(problem)
		if info is not None:
			proc.update(info)
		if self._include_gt_info:
			proc['problem'] = problem

		question = self.task.observe(problem, seed=self._master_seed)

		failed = False
		with self.strategy.collect_stats() as stats:
			try:
				response, steps = self.strategy.solve(question, side_information=info)
			except StrategyFailure as e:
				response = str(e) if type(e) == StrategyFailure else f'{e.__class__.__name__}: {e}'
				steps = {'error': type(e).__name__, 'error_message': str(e), 'traceback': traceback.format_exc()}
				failed = True
		if len(stats):
			log.update(stats)
		if steps is not None:
			proc.update(steps)
		proc['response'] = response

		if failed:
			decision = None
			verdict = None
		elif self.judge is None:
			decision = response
			verdict = decision == answer
		else:
			with self.judge.collect_stats() as judge_stats:
				decision, judgement = self.judge.interpret(question, response)
				verdict = self.judge.judge(decision, answer, judgement)
			if len(judge_stats):
				log['judge'] = judge_stats
			if judgement is not None:
				proc.update(judgement)
			failed = verdict is None

		score = self._aggregate_verdict(idx, verdict)
		proc['decision'] = decision
		proc['answer'] = answer
		proc['verdict'] = verdict

		sample = {}
		if len(log):
			sample['log'] = log
		if len(proc):
			sample['table'] = proc

		sample['score'] = score
		sample['failed'] = failed
		if failed:
			self._past_failures += 1
		self._past_iterations += 1
		sample['fail_rate'] = self._past_failures / self._past_iterations
		log['fail_rate'] = sample['fail_rate']
		return sample

	def _aggregate_verdict(self, idx: int = None, verdict: JSONABLE = None):
		if verdict is not None:
			if self._answer_type == 'yes/no':
				self.metrics['correct' if verdict else 'incorrect'].append(idx)
				N_cor = len(self.metrics['correct'])
				N_inc = len(self.metrics['incorrect'])
				N = N_cor + N_inc
				acc = N_cor / N if N > 0 else 0
				return acc
			elif isinstance(self._answer_type, list):
				for key, val in verdict.items():
					if val is not None:
						self.metrics.setdefault(key, []).append(val)
				return {key: sum(vals) / len(vals) for key, vals in self.metrics.items() if len(vals)}
			elif self._answer_type is None:
				pass
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
		info = {
			# 'seed': self._master_seed,
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

		if self._answer_type == 'yes/no':
			N_cor = len(self.metrics['correct'])
			N_inc = len(self.metrics['incorrect'])
			N = N_cor + N_inc
			acc = N_cor / N if N > 0 else 0
			info.update({
				'total': N,
				'correct': N_cor,
				'incorrect': N_inc,
				'accuracy': acc,
			})
		elif isinstance(self._answer_type, list):
			means = {key: sum(vals) / len(vals) for key, vals in self.metrics.items() if len(vals)}
			metrics = {key: vals.copy() for key, vals in self.metrics.items() if len(vals)}
			info.update({'means': means, 'metrics': metrics, })
		elif self._answer_type is None:
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




