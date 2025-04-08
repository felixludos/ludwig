from .imports import *
from ..abstract import AbstractTask, AbstractStrategy, AbstractProtocol
# from ..base import Task, Strategy
import pandas as pd

try:
	import wandb
except ImportError:
	wandb = None


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

	ckpt_freq = cfg.pulls('ckpt-freq', 'ckpt', default=None)

	cfg.push('protocol._type', 'default-protocol', overwrite=False, silent=True)
	protocol: AbstractProtocol = cfg.pull('protocol')

	protocol.prepare()

	out_dir = None
	if out_root is not None:
		if protocol.name is None:
			raise ValueError(f'Protocol must have a name: {protocol.name}')
		out_dir = out_root / protocol.name
		if out_dir.exists() and not cfg.pull('overwrite', False):
			raise RuntimeError(f'Output directory {out_dir} already exists. Use --overwrite to overwrite it.')
		out_dir.mkdir(exist_ok=True)

	wandb_run = None
	check_confirmation = None
	if use_wandb:
		wandb_run = wandb.init(project=protocol.task.name, config=protocol.json(), dir=out_dir)
		wandb_addr = f'{wandb_run.entity}/{wandb_run.project}/{wandb_run.id}'
		if pause_after:
			check_confirmation = lambda: 'confirm' in wandb.apis.public.Api().run(wandb_addr).tags

	desc = protocol.describe()
	if desc is not None:
		print(desc)
		print()
	if out_dir is not None:
		print(f'Saving results to {out_dir}')
		print()

	artifacts = protocol.pre_loop()

	itr = protocol.remaining_iterations()
	num_digits = len(str(len(itr))) + 1
	if out_dir is not None and ckpt_freq is not None:
		ckptpath = out_dir / f'ckpt-{0:0{num_digits}}'
		protocol.checkpoint(ckptpath)
		if artifacts is not None:
			with ckptpath.joinpath('artifacts.json').open('w') as f:
				json.dump(artifacts, f)

	if pbar: itr = tqdm(itr, desc=f'{protocol.name}')
	for i in itr:
		sample = protocol.step(i)
		if 'message' in sample:
			print()
			print(sample['message'])
			del sample['message']
		if 'pbar' in sample:
			assert pbar
			itr.set_description(sample['pbar'])
			del sample['pbar']
		if wandb_run is not None and (pause_after is None or i <= pause_after):
			if 'log' in sample:
				wandb_run.log(sample['log'])
			if 'table' in sample:
				# columns = shutil.get_terminal_size(fallback=(60, 20)).columns
				# tbl = {key: wrap_text(val, max(columns, 60)) for key, val in flatten(sample['table']).items()}
				tbl = {key: str(val) for key, val in flatten(sample['table']).items()}
				if isinstance(tbl, dict):
					# convert dict[str,str] to dataframe
					tbl = pd.DataFrame(tbl.items(), columns=['Key', 'Value'])
				if isinstance(tbl, pd.DataFrame):
					tbl = wandb.Table(dataframe=tbl)
				wandb_run.log({'table': tbl})
		if out_dir is not None and ckpt_freq is not None and i > 0 and i % ckpt_freq == 0:
			protocol.checkpoint(out_dir / f'ckpt-{i+1:0{num_digits}}')

	summary = protocol.summary()
	if summary is not None:
		print(summary)
		print()

	if out_dir is not None:
		protocol.checkpoint(out_dir)

	out = protocol.post_loop()

	if wandb_run is not None:
		wandb_run.finish()

	return out



@fig.script('validate', description='Check what a `task` is missing and what it implements')
def validate_task(cfg: fig.Configuration):
	"""
	Validate a `task` - checks what features the task implements and if something's missing
	"""

	task: AbstractTask = cfg.pull('task')

	raise NotImplementedError('todo')

