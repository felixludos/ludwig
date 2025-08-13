from .imports import *
from ..abstract import AbstractTask


@fig.component('stub-task')
class StubTask(AbstractTask):
	"""
	A task that runs for a fixed number of iterations.
	"""

	def __init__(self, n: int, seed: int = 1000000009, *,
				 index_key: str = 'index', seed_key: str = 'seed', **kwargs):
		super().__init__(**kwargs)
		self.n = n
		self.master_seed = seed
		self.index_key = index_key
		self.seed_key = seed_key
		self._rng = random.Random(seed)
		self._seed_cache = []

	@property
	def name(self) -> str:
		return f'stub{self.n}'

	@property
	def is_judge(self):
		return False

	def store_keys(self) -> Iterator[str]:
		yield self.index_key
		yield self.seed_key

	def show_keys(self) -> Iterator[str]:
		yield self.index_key
		yield self.seed_key

	def status(self) -> Optional[JSONOBJ]:
		return {}

	def resolve(self, problem: JSONOBJ, response: JSONOBJ) -> JSONOBJ:
		pass

	def json(self) -> JSONOBJ:
		return {'n': self.n, 'master_seed': self.master_seed,
				'index_key': self.index_key, 'seed_key': self.seed_key}

	def context(self) -> str:
		return ''

	def description(self) -> str:
		return ''

	def specification(self) -> JSONOBJ:
		return {}

	def checkpoint(self, path: Optional[Path] = None) -> Optional[JSONOBJ]:
		pass

	@property
	def total_questions(self) -> Optional[int]:
		return self.n

	def ask(self, index: int) -> JSONOBJ:
		return {self.index_key: index, self.seed_key: self._get_seed(index)}

	def _get_seed(self, idx: int):
		assert idx >= 0, 'Index must be non-negative'
		while idx > len(self._seed_cache) - 1:
			self._seed_cache.append(self._rng.randint(0, 2**31 - 1))
		return self._seed_cache[idx]

