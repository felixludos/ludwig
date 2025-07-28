from .imports import *
from ..abstract import AbstractTask, AbstractStrategy, AbstractProtocol
from ..util import AbstractBroker, DefaultBroker
# from ..base import Task, Strategy
import pandas as pd
from os import symlink, environ

try:
	import wandb
except ImportError:
	wandb = None

def _view_score(score, fail_rate=None):
	if fail_rate is not None:
		return f'{_view_score(score)} ({fail_rate:.0%})'
	if score is None:
		return
	if isinstance(score, float):
		return f'{score:.2f}'
	elif isinstance(score, dict): # TODO flatten first
		return ', '.join([f'{k}={_view_score(v)}' for k, v in score.items()])
	raise ValueError('score must be float or dict')


@fig.script('eval', description='Evaluate a `task` on a `strategy` (i.e. model)')
def eval_task(cfg: fig.Configuration):
	"""
	Evaluate a `strategy` on a specific `task` (using a specific `protocol`).

	Optionally saves results to a directory with `out-dir` as the root.

	:param task: The task to evaluate.
	:type task: AbstractTask
	:param strategy: The strategy to evaluate (ie. the model).
	:type strategy: AbstractStrategy
	:param protocol: The protocol to use for evaluation.
	:type protocol: AbstractProtocol
	:return:
	"""
	environ['WANDB_PROGRAM'] = 'eval'
	limit = cfg.pull('limit', None)

	out_root = cfg.pull('root', None)
	if out_root is not None:
		out_root = Path(out_root)
		out_root.mkdir(exist_ok=True)

	resume = cfg.pull('resume', None)
	if resume is None:
		cfg.push('protocol._type', 'default-protocol', overwrite=False, silent=True)
		ckptpath = None
	else:
		out_dir = out_root / resume
		assert out_dir.exists(), f'Cannot resume from {out_dir}, it does not exist'
		cfgpath = out_dir / 'config.yaml'
		assert cfgpath.exists(), f'Cannot resume from {out_dir}, config file does not exist'
		loadcfg = fig.create_config(cfgpath)
		loadcfg.update(cfg)
		# find/load checkpoint
		ckpts = list(out_dir.glob('ckpt-*'))
		if len(ckpts) == 0:
			raise ValueError(f'No checkpoints found in {out_dir}')
		ckptpath = max(ckpts, key=lambda p: (p.name, p.stat().st_mtime))

	protocol: AbstractProtocol = cfg.pull('protocol')

	if ckptpath is not None:
		if not ckptpath.exists():
			raise ValueError(f'Checkpoint path {ckptpath} does not exist')
		protocol.load_checkpoint(ckptpath)

	pbar: bool = cfg.pull('pbar', where_am_i() != 'cluster')
	print_freq = None
	if pbar:
		pbar_desc = cfg.pull('pbar-desc', '{"[score]" if score is None else f"{score:.2%}"} '
										  '(fail={fails}, invalid={invalid})')
	else:
		print_freq = cfg.pull('print-freq', None)

	use_wandb = cfg.pulls('use-wandb', 'wandb', default=wandb is not None and out_root is not None)
	pause_after = None
	if use_wandb and wandb is None:
		raise ValueError('You need to install `wandb` to use `wandb`')
	if use_wandb:
		pause_after = cfg.pull('pause-after', None)
		shutdown_period = cfg.pull('shutdown-period', 60) # in sec

	logger = cfg.pull('logger', None)
	prelogger = cfg.pull('prelogger', None)
	viewer = cfg.pull('viewer', None)
	results = cfg.pull('results', None)

	ckpt_freq = cfg.pulls('ckpt-freq', 'ckpt', default=None)
	error_ckpt = cfg.pull('err-ckpt', True)

	protocol.prepare()

	if out_root is None:
		out_dir = None
		if use_wandb:
			raise ValueError('You need to specify `root` to use `wandb`')
	else:
		out_dir = out_root / protocol.name
		out_dir.mkdir(parents=False, exist_ok=True)

	wandb_run = None
	check_confirmation = None
	check_shutdown = None
	if use_wandb and out_dir is not None:
		wandb_dir = out_dir.absolute()
		wandb_config = protocol.json()
		project_name = cfg.pull('project-name', '{task.name}')
		project_name = pformat(project_name, protocol=protocol, task=protocol.task, config=wandb_config)
		wand_id = None
		if resume is not None:
			# get wandb entity
			entity = cfg.pull('wandb-entity', 'felixludos')
			api = wandb.Api()
			runs = api.runs(f'{entity}/{project_name}', filters={'display_name': resume})
			if len(runs) == 0:
				raise RuntimeError(f'No runs found with name {resume}')
			if len(runs) > 1:
				raise RuntimeError(f'Multiple runs found with name {resume}')
			wandb_run = runs[0]
			wand_id = wandb_run.id
		wandb_run = wandb.init(project=project_name, name=protocol.name, config=wandb_config, dir=wandb_dir, id=wand_id)
		wandb_addr = f'{wandb_run.entity}/{wandb_run.project}/{wandb_run.id}'
		if pause_after:
			check_confirmation = lambda: 'confirm' in wandb.apis.public.Api().run(wandb_addr).tags
		check_shutdown = lambda: 'shutdown' in wandb.apis.public.Api().run(wandb_addr).tags

		if viewer is not None and len(viewer):
			print('Viewer:')
			print(viewer.describe())
		else:
			print(f'Not viewing anything.')

		protocol.remember(wandb={'id': wandb_run.id, 'entity': wandb_run.entity, 'project': wandb_run.project})

	desc = protocol.describe()
	if desc is not None:
		print(desc)
		print()

	sample_logger = None
	if out_dir is not None:
		with out_dir.joinpath('config.yaml').open('w') as f:
			f.write(str(cfg))
		if logger is not None and len(logger):
			print('Logging:')
			print(logger.describe())
			sample_logger = out_dir.joinpath('log.jsonl').open('a')
		else:
			print(f'Not logging anything.')

	if out_dir is not None:
		print(f'Output dir: {out_dir}')
		print()

	artifacts = protocol.pre_loop()
	if artifacts is not None:
		if 'stats' in artifacts:
			print(f'Pre-loop stats:')
			print(tabulate(flatten(artifacts['stats']).items()))
		if prelogger is not None and len(prelogger):
			pre = prelogger.extract(artifacts)
			if use_wandb and len(pre):
				pre = {f'pre/{k}': v for k, v in flatten(pre).items()}
				wandb_run.log({f'pre': pre}, step=0)

	itr = protocol.remaining_iterations(limit)
	n_itr = len(itr)
	if pbar is None and print_freq is None:
		print_freq = max(n_itr//200, 1)
	num_digits = len(str(n_itr)) + 1
	if out_dir is not None and ckpt_freq is not None:
		ckptpath = out_dir / f'ckpt-{0:0{num_digits}}'
		protocol.checkpoint(ckptpath)
		if artifacts is not None:
			with ckptpath.joinpath('artifacts.json').open('w') as f:
				json.dump(artifacts, f)

	if pbar: itr = tqdm(itr, desc=f'[score]')
	ckpted = False
	shutdown_time = time.time()
	i = 0
	for i in itr:
		ckpted = False
		try:
			sample = protocol.step(i)
		except:
			if out_dir is not None and error_ckpt:
				ckptpath = out_dir / f'ckpt-{i:0{num_digits}}'
				protocol.checkpoint(path=out_dir / f'error{i}')
				print(f'Checkpointed error at iteration {i} to {out_dir / f"error{i}"}')
			raise
		if pbar and pbar_desc is not None:
			itr.set_description(pformat(pbar_desc, sample))
		if print_freq is not None:
			raise NotImplementedError
		if sample_logger is not None and len(logger):
			log = logger.extract(sample)
			sample_logger.write(json.dumps(log) + '\n')
			sample_logger.flush()
		if wandb_run is not None:
			if viewer is not None and len(viewer):
				viz = viewer.extract(sample)
				if len(viz):
					viz = {f'live/{k}': v for k, v in flatten(viz).items()}
					wandb_run.log(viz, step=i)
		if wandb_run is not None and (time.time() - shutdown_time) >= shutdown_period:
			shutdown_time = time.time()
			if check_shutdown():
				ckptpath = out_dir / f'ckpt-{i + 1:0{num_digits}}'
				protocol.checkpoint(ckptpath)
				print(f'Received shutdown signal, checkpointed at: {ckptpath}')
				return
		if out_dir is not None and i > 0 and ckpt_freq is not None and i % ckpt_freq == 0:
			ckptpath = out_dir / f'ckpt-{i + 1:0{num_digits}}'
			protocol.checkpoint(ckptpath)
			ckpted = True

	summary = protocol.summary()
	if summary is not None:
		print(summary)

	remaining = protocol.remaining_iterations()
	if remaining:
		print(f'Remaining iterations: {len(remaining)}')

	if sample_logger is not None:
		sample_logger.close()

	if out_dir is not None and not ckpted:
		ckptpath = out_dir / f'ckpt-{i + 1:0{num_digits}}'
		protocol.checkpoint(ckptpath)
		print(f'Checkpointed final state to {ckptpath}')
		latest_ckpt = out_dir / 'ckpt-final'
		if latest_ckpt.exists():
			latest_ckpt.unlink()
		latest_ckpt.symlink_to(ckptpath.name)
		
	out = protocol.post_loop()
	if results is not None and len(results):
		out = results.extract(out)

	if wandb_run is not None:
		# if viewer is not None and len(viewer):
		# 	viz = viewer.extract(sample)
		# 	if len(viz):
		# 		viz = {f'{k}': v for k, v in flatten(viz).items()}
		# 		wandb_run.log(viz, step=i)
		wandb.summary.update(out)
		wandb_run.finish()
	return out



@fig.script('validate', description='Check what a `task` is missing and what it implements')
def validate_task(cfg: fig.Configuration):
	"""
	Validate a `task` - checks what features the task implements and if something's missing
	"""

	task: AbstractTask = cfg.pull('task')

	raise NotImplementedError('todo')

