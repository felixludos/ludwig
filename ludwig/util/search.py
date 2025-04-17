from .imports import *



class AbstractSearch:
	"""Generic search routines."""
	pass



T = TypeVar('T')

class NaiveSearch(fig.Configurable, AbstractSearch):
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
	


class GenericSearch(fig.Configurable, AbstractSearch):
	def __init__(self, *, breadth_first: bool = True, 
			  max_depth: Optional[int] = None, fuel: Optional[int] = None, **kwargs):
		super().__init__(**kwargs)
		self.breadth_first = breadth_first
		self.max_depth = max_depth
		self.fuel = fuel


		self.namespace = {}
		self.expand_fn_name = None
		self.select_fn_name = None
		self.extract_fn_name = None
		self.evaluate_fn_name = None

	def include_expand_items(self, items: Dict[str, Any], *, expand_fn_name: str = 'expand') -> Iterable[T]:
		self.namespace.update(items)
		self.expand_fn_name = expand_fn_name
		return self
	
	def include_select_items(self, items: Dict[str, Any], *, select_fn_name: str = 'select') -> Iterable[T]:
		self.namespace.update(items)
		self.select_fn_name = select_fn_name
		return self
	
	def include_extract_items(self, items: Dict[str, Any], *, extract_fn_name: str = 'extract') -> Iterable[T]:
		self.namespace.update(items)
		self.extract_fn_name = extract_fn_name
		return self
	
	def include_evaluate_items(self, items: Dict[str, Any], *, evaluate_fn_name: str = 'evaluate') -> Iterable[T]:
		self.namespace.update(items)
		self.evaluate_fn_name = evaluate_fn_name
		return self
	
	def include_policy_items(self, items: Dict[str, Any], *, policy_fn_name: str = 'policy') -> Iterable[T]:
		self.namespace.update(items)
		self.policy_fn_name = policy_fn_name
		return self
	
	def include_step_items(self, items: Dict[str, Any], *, step_fn_name: str = 'step') -> Iterable[T]:
		self.namespace.update(items)
		self.step_fn_name = step_fn_name
		return self











