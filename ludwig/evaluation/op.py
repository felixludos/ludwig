from .imports import *
from ..abstract import AbstractTask, AbstractStrategy, AbstractProtocol
from ..util import AbstractBroker, DefaultBroker
# from ..base import Task, Strategy
import pandas as pd

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
	out_root = cfg.pull('out-dir', None)
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

	use_wandb = cfg.pulls('use-wandb', 'wandb', default=wandb is not None)
	pause_after = None
	if use_wandb and wandb is None:
		raise ValueError('You need to install `wandb` to use `wandb`')
	if use_wandb:
		pause_after = cfg.pull('pause-after', None)

	logger = cfg.pull('logger', None)
	viewer = cfg.pull('viewer', None)
	results = cfg.pull('results', None)

	ckpt_freq = cfg.pulls('ckpt-freq', 'ckpt', default=None)
	error_ckpt = cfg.pull('err-ckpt', True)

	out_dir = protocol.prepare(out_root)

	wandb_run = None
	check_confirmation = None
	if use_wandb:
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
		if use_wandb and 'study' in artifacts:
			tbl = {key: str(val) for key, val in flatten(artifacts['study']).items()}
			if isinstance(tbl, dict):
				# convert dict[str,str] to dataframe
				tbl = pd.DataFrame(tbl.items(), columns=['Key', 'Value'])
			if isinstance(tbl, pd.DataFrame):
				tbl = wandb.Table(dataframe=tbl)
			wandb_run.log({f'study': tbl})

	limit = cfg.pull('limit', None)
	itr = protocol.remaining_iterations(limit)
	n_itr = len(itr)
	pbar_desc = None
	print_freq = None
	if pbar:
		pbar_desc = cfg.pull('pbar-desc', '{"[score]" if sample.get("score") is None else f"{score:.2%}"} '
										  '(fail={fails}, invalid={invalid})')
	else:
		print_freq = cfg.pull('print-freq', max(n_itr//200, 1))
	num_digits = len(str(n_itr)) + 1
	if out_dir is not None and ckpt_freq is not None:
		ckptpath = out_dir / f'ckpt-{0:0{num_digits}}'
		protocol.checkpoint(ckptpath)
		if artifacts is not None:
			with ckptpath.joinpath('artifacts.json').open('w') as f:
				json.dump(artifacts, f)

	if pbar: itr = tqdm(itr, desc=f'[score]')
	for i in itr:
		try:
			sample = protocol.step(i)
		except:
			if out_dir is not None and error_ckpt:
				ckptpath = out_dir / f'ckpt-{i:0{num_digits}}'
				protocol.checkpoint(path=out_dir / f'error{i}', force=True)
				print(f'Checkpointed error at iteration {i} to {out_dir / f"error{i}"}')
			raise
		if pbar and pbar_desc is not None:
			itr.set_description(pformat(pbar_desc, sample))
		if print_freq is not None:
			raise NotImplementedError
		if wandb_run is not None and (pause_after is None or i <= pause_after):
			# if 'log' in sample:
			# 	wandb_run.log(flatten(sample['log']))
			if 'table' in sample and (log_table is None or (i < log_table)):
				# columns = shutil.get_terminal_size(fallback=(60, 20)).columns
				# tbl = {key: wrap_text(val, max(columns, 60)) for key, val in flatten(sample['table']).items()}
				tbl = {key: str(val) for key, val in flatten(sample['table']).items()}
				if isinstance(tbl, dict):
					# convert dict[str,str] to dataframe
					tbl = pd.DataFrame(tbl.items(), columns=['Key', 'Value'])
				if isinstance(tbl, pd.DataFrame):
					tbl = wandb.Table(dataframe=tbl)
				wandb_run.log({f'table{i}': tbl}, step=i)
			elif 'table' in sample and log_fails and sample.get('failed'):
				tbl = {key: str(val) for key, val in flatten(sample['table']).items()}
				if isinstance(tbl, dict):
					# convert dict[str,str] to dataframe
					tbl = pd.DataFrame(tbl.items(), columns=['Key', 'Value'])
				if isinstance(tbl, pd.DataFrame):
					tbl = wandb.Table(dataframe=tbl)
				wandb_run.log({f'fail{i}': tbl}, step=i)
				if isinstance(log_fails, int):
					log_fails -= 1
					if log_fails <= 0:
						log_fails = None
			if 'score' in sample and sample['score'] is not None:
				scores = {'score': sample['score']} if isinstance(sample['score'], (int,float)) else sample['score']
				wandb_run.log({f'live-{key}': val for key, val in flatten(scores).items()}, step=i)
			if 'log' in sample:
				wandb_run.log(flatten(sample['log']), step=i)
		if sample_logger is not None:
			if drop_keys:
				drop_keys_in_sample(sample, drop_keys)
			sample_logger.write(json.dumps(sample) + '\n')
			sample_logger.flush()
		if out_dir is not None and ckpt_freq is not None and i > 0 and i % ckpt_freq == 0:
			protocol.checkpoint(out_dir / f'ckpt-{i+1:0{num_digits}}')

	summary = protocol.summary()
	if summary is not None:
		print(summary)
		print()

	remaining = protocol.remaining_iterations()
	if remaining:
		print(f'Remaining iterations: {remaining}')

	if sample_logger is not None:
		sample_logger.close()

	if out_dir is not None:
		protocol.checkpoint(out_dir)

	out = protocol.post_loop()

	if wandb_run is not None:
		wandb.summary.update(flatten(out))
		wandb_run.finish()

	return out



@fig.script('validate', description='Check what a `task` is missing and what it implements')
def validate_task(cfg: fig.Configuration):
	"""
	Validate a `task` - checks what features the task implements and if something's missing
	"""

	task: AbstractTask = cfg.pull('task')

	raise NotImplementedError('todo')

