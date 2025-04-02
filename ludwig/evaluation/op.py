from .imports import *
from ..abstract import AbstractTask, AbstractSubject, AbstractProtocol
# from ..base import Task, Subject


@fig.script('eval')
def eval_task(cfg: fig.Configuration):

	pbar: bool = cfg.pull('pbar', True)

	seed: Optional[int] = cfg.pull('seed', None) # 2131131137
	if seed is None:
		seed = random.randint(0, 2**31 - 1)
	random.seed(seed)
	seeder = random.Random(seed)

	out_root = cfg.pull('out-dir', None)
	if out_root is not None:
		out_root = Path(out_root)
		out_root.mkdir(exist_ok=True)

	protocol: AbstractProtocol = cfg.pull('protocol')

	task: AbstractTask = cfg.pull('task')

	subject: AbstractSubject = cfg.pull('subject')

	limit: int = cfg.pulls('limit', 'n', default=None)

	out_dir = None
	if out_root is not None:
		out_name = cfg.pull('out-name', '{task.name}_{subject.name}_{now:%Y-%m-%d_%H-%M-%S}')
		out_dir = out_root / out_name.format(task=task, subject=subject, now=now, seed=seed)
		if out_dir.exists() and not cfg.pull('overwrite', False):
			raise RuntimeError(f'Output directory {out_dir} already exists. Use --overwrite to overwrite it.')
		out_dir.mkdir(exist_ok=True)

	task.setup(seed)

	subject.prepare(task)

	print(f'Protocol: {protocol.name}')
	print(f'Task: {task.name}')
	print(f'Subject: {subject.name}')
	print(f'Random seed: {seed}')
	if limit is not None:
		print(f'Limit: {limit}')
	print()
	print(f'Saving results to {out_dir}')

	max_num = task.total_questions
	N = max_num
	if N is None:
		if limit is None:
			raise RuntimeError('Task has no total_questions and no limit was provided.')
		N = limit

	itr = range(N)
	if pbar:
		itr = tqdm(itr, desc='Questions', total=N)


	subject.


	for i in itr:
		sample_seed = seeder.randint(0, 2**31 - 1)

		problem, answer = task.generate(sample_seed) if max_num is None else task.load(i, seed=sample_seed)

		info = task.side_information(problem)



		pass

	pass

