from .imports import *
from ..abstract import AbstractTask, AbstractStrategy, AbstractProtocol
# from ..base import Task, Strategy


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

	pbar: bool = cfg.pull('pbar', True)

	out_root = cfg.pull('out-dir', None)
	if out_root is not None:
		out_root = Path(out_root)
		out_root.mkdir(exist_ok=True)

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

	desc = protocol.describe()
	if desc is not None:
		print(desc)
		print()
	if out_dir is not None:
		print(f'Saving results to {out_dir}')
		print()

	artifacts = protocol.pre_loop()

	itr = protocol.remaining_iterations()
	if pbar: itr = tqdm(itr, desc=f'{protocol.name}')
	for i in itr:
		sample = protocol.step(i)
		if 'message' in sample:
			print()
			print(sample['message'])
		if 'pbar' in sample:
			assert pbar
			itr.set_description(sample['pbar'])

	summary = protocol.summary()
	if summary is not None:
		print(summary)
		print()

	out = protocol.post_loop()
	return out



@fig.script('validate', description='Check what a `task` is missing and what it implements')
def validate_task(cfg: fig.Configuration):
	"""
	Validate a `task` - checks what features the task implements and if something's missing
	"""

	task: AbstractTask = cfg.pull('task')

	raise NotImplementedError('todo')

