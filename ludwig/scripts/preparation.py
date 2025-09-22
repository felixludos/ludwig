from ..imports import *
from ..errors import OptionalMethodNotImplemented



@fig.script('download')
def download_task_assets(cfg: fig.Configuration):

	task = cfg.pull('task', None)
	if task is None:
		raise ValueError('No task specified (use `task`)')

	try:
		path = task.download()
	except OptionalMethodNotImplemented:
		print(f'Task {task} hast not implemented the `download` method (so there is probably nothing to download)')
	else:
		if path is not None:
			print(f'Downloaded assets for {task} to {path}')

	print(f'Checking if task can be prepared...')

	task.prepare()

	print(f'Task {task} is prepared and ready to use.')



