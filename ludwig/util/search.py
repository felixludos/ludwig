from .imports import *



class AbstractSearch:
	"""Generic search routines."""
	pass


T = TypeVar('T')

class NaiveSearch(AbstractSearch):
	# Generic search API requiring two functions: expand and evaluate
	# expand: T -> Iterable[T] - returns the possible next states from a given state
	# evaluate: Iterable[T] -> Optional[str] - returns a message if the trajectory is complete, otherwise None



	@classmethod
	def search_step(cls, traj: Iterable[T], expand: Callable[[T], Iterable[T]], evaluate: Callable[[Iterable[T]], Optional[str]]) -> Iterable[T]:
		out = evaluate(list(traj))
		if out is None:
			for next_state in expand(traj[-1]):
				yield from cls.search_step((*traj, next_state,), expand, evaluate)
		else:
			yield out
			
	@classmethod
	def search(cls, init_state: T, expand: Callable[[T], Iterable[T]], evaluate: Callable[[Iterable[T]], Optional[str]]) -> Iterable[T]:
		return cls.search_step((init_state,), expand, evaluate)
	











