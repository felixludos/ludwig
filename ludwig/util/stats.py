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



class ClientStats(AbstractStats):
	def __init__(self, client: AbstractClient, *, include_start: bool = False):
		self.client = client
		self.include_start = include_start
		self.starting_idx = None
		self.stats = {}

	def __enter__(self) -> JSONOBJ:
		self.stats['start'] = time.time()
		self.starting_idx = self.client.past_requests()
		return self.stats

	def __exit__(self, exc_type, exc_val, exc_tb):
		self.stats['time'] = time.time() - self.stats['start']
		if not self.include_start:
			del self.stats['start']
		self.stats.update(self.client.stats(starting_from=self.starting_idx))

