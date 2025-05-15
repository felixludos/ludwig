from .imports import *
from ..abstract import AbstractTask, AbstractStrategy, AbstractProtocol
# from ..base import Task, Strategy
import pandas as pd

try:
	import wandb
except ImportError:
	wandb = None

def drop_keys_in_sample(sample, drop_keys):
	for key in drop_keys:
		loc = sample
		while len(key):
			x, *terms = key.split('.')
			key = '.'.join(terms)
			if isinstance(loc, dict):
				if x in loc:
					if len(terms):
						loc = loc[x]
					else:
						del loc[x]
						break
				else:
					break
			else:
				break

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
	pbar: bool = cfg.pull('pbar', where_am_i() != 'cluster')

	use_wandb = cfg.pulls('use-wandb', 'wandb', default=wandb is not None)
	pause_after = None
	if use_wandb and wandb is None:
		raise ValueError('You need to install `wandb` to use `wandb`')
	if use_wandb:
		pause_after = cfg.pull('pause-after', None)

	out_root = cfg.pull('out-dir', None)
	if out_root is not None:
		out_root = Path(out_root)
		out_root.mkdir(exist_ok=True)

	log_table = cfg.pull('log-table', 4)
	log_fails = cfg.pull('log-fails', 10)
	log_samples = cfg.pull('log-samples', (not use_wandb or log_table is not None) and out_root is not None)
	drop_keys = cfg.pull('drop-keys', [])

	ckpt_freq = cfg.pulls('ckpt-freq', 'ckpt', default=None)
	error_ckpt = cfg.pull('err-ckpt', True)

	cfg.push('protocol._type', 'default-protocol', overwrite=False, silent=True)
	protocol: AbstractProtocol = cfg.pull('protocol')

	out_dir = protocol.prepare(out_root)

	if out_dir is not None:
		with out_dir.joinpath('config.yaml').open('w') as f:
			f.write(str(cfg))

	wandb_run = None
	check_confirmation = None
	if use_wandb:
		wandb_dir = out_dir.absolute()
		wandb_config = protocol.json()
		project_name = cfg.pull('project-name', '{task.name}')
		project_name = pformat(project_name, protocol=protocol, task=protocol.task, config=wandb_config)
		wandb_run = wandb.init(project=project_name, name=protocol.name, config=wandb_config, dir=wandb_dir)
		wandb_addr = f'{wandb_run.entity}/{wandb_run.project}/{wandb_run.id}'
		if pause_after:
			check_confirmation = lambda: 'confirm' in wandb.apis.public.Api().run(wandb_addr).tags

	sample_logger = None
	if log_samples:
		assert out_dir is not None, f'log-samples requires out-dir to be set'
		sample_logger = out_dir.joinpath('log.jsonl').open('a')

	desc = protocol.describe()
	if desc is not None:
		print(desc)
		print()
	if out_dir is not None:
		print(f'Saving results to {out_dir}')
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

	itr = protocol.remaining_iterations()
	num_digits = len(str(len(itr))) + 1
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
				protocol.checkpoint(out_dir / f'error{i}')
			raise
		if 'message' in sample:
			print()
			print(sample['message'])
			del sample['message']
		if 'score' in sample and pbar:
			score = _view_score(sample['score'], sample.get('fail_rate'))
			itr.set_description(score)
		elif 'pbar' in sample and pbar:
			itr.set_description(sample['pbar'])
			del sample['pbar']
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

