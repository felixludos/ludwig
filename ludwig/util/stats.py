from .imports import *
from .clients import AbstractClient



class AbstractStats:
	def __enter__(self) -> JSONOBJ:
		raise NotImplementedError

	def __exit__(self, exc_type, exc_val, exc_tb):
		raise NotImplementedError



class EmptyStats(AbstractStats):
	def __enter__(self) -> JSONOBJ:
		return {}

	def __exit__(self, exc_type, exc_val, exc_tb):
		pass



class TimeStats(AbstractStats):
	def __init__(self, *, include_start: bool = False):
		self.include_start = include_start
		self.stats = {}

	def __enter__(self) -> JSONOBJ:
		self.stats['start'] = time.time()
		return self.stats

	def __exit__(self, exc_type, exc_val, exc_tb):
		if exc_type is None:
			self.stats['time'] = time.time() - self.stats['start']
			if not self.include_start:
				del self.stats['start']



class ClientStats(TimeStats):
	def __init__(self, client: AbstractClient, **kwargs):
		super().__init__(**kwargs)
		self.client = client
		self.starting_idx = None

	def __enter__(self) -> JSONOBJ:
		out = super().__enter__()
		self.starting_idx = self.client.past_requests()
		return out

	def __exit__(self, exc_type, exc_val, exc_tb):
		out = super().__exit__(exc_type, exc_val, exc_tb)
		if exc_type is None:
			self.stats.update(self.client.stats(starting_from=self.starting_idx))
		return out


import subprocess

def get_git_commit_hash() -> str:
    """Gets the current git commit hash."""
    try:
        # Run the git command to get the short commit hash
        commit_hash = subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'],
            stderr=subprocess.STDOUT
        ).strip().decode('utf-8')
        return commit_hash
    except subprocess.CalledProcessError as e:
        print(f"Error: {e.output.decode('utf-8').strip()}")
        return "Not a git repository or git not installed."
    except FileNotFoundError:
        return "Git is not installed or not in the system's PATH."



