from .imports import *



class AbstractSearch:
	"""Generic search routines."""
	pass



T = TypeVar('T')



@fig.component('generic')
class GenericSearch(fig.Configurable, AbstractSearch):
	def __init__(self, *, check_first: Optional[int] = None, markovian: bool = False,
			  max_depth: Optional[int] = None, fuel: Optional[int] = None, **kwargs):
		assert check_first is None or check_first > 0, f'check_first must be a positive integer or None, got {check_first}'
		assert max_depth is None or max_depth > 0, f'max_depth must be a positive integer or None, got {max_depth}'
		assert fuel is None or fuel > 0, f'fuel must be a positive integer or None, got {fuel}'
		super().__init__(**kwargs)
		
		self.check_first = check_first
		self.markovian = markovian
		self.max_depth = max_depth
		self.fuel = fuel

	def json(self):
		return {
			'check_first': self.check_first,
			'markovian': self.markovian,
			'max_depth': self.max_depth,
			'fuel': self.fuel,
		}

	@staticmethod
	def _current_paths(past: Iterable[T], source: Iterable[T]) -> Iterator[List[T]]:
		for current in source:
			yield [*past, current]
			
	def run(self, init_state: T, *, expand_fn: Callable[[List[T]], Iterable[T]],
			extract_fn: Callable[[List[T]], Optional[str]]) -> Iterator[str]:
		waiting = deque()
		waiting.append(self._current_paths((), [init_state]))

		if self.markovian:
			expand_fn = lambda traj: expand_fn(traj[-1])

		n = 0
		while waiting:
			source = waiting.popleft()

			for i, traj in enumerate(source):
				result = extract_fn(traj)
				if result is not None:
					yield result

				n += 1
				if n >= self.fuel:
					return
				
				if result is not None or (self.max_depth is not None and len(traj) >= self.max_depth):
					continue
				
				new_source = expand_fn(traj)
				waiting.append(self._current_paths(traj, new_source))
				
				if self.check_first is not None and i+1 == self.check_first:
					waiting.append(source)
					break










