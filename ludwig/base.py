from .imports import *
from .abstract import AbstractTool, AbstractTask, AbstractSubject, AbstractProtocol, PROBLEM, ANSWER
from .errors import ToolError, OptionalMethodNotImplemented, AmbiguousFormalizationError



class LLM_Tool(AbstractTool):
	pass



class Task(AbstractTask):
	def generate(self, seed: int) -> Tuple[PROBLEM, ANSWER]:
		"""
		Generates a specific question and associated ground-truth answer.

		Note that the representation of the problem and answer can be anything (json parsable), provided it fully
		specifies a specific question and associated (unambiguous) ground-truth expected behavior/answer.

		:param seed: optional to ensure deterministic behavior
		"""
		if self.total_questions is not None:
			return self.load(seed % self.total_questions, seed=seed)
		raise NotImplementedError

	def setup(self, seed: int) -> None:
		"""
		(optional) Setup any necessary state for this task

		This is called before the task is used, and can be used to initialize any state or configuration.

		:param seed: optional to ensure deterministic behavior
		"""
		pass

	def side_information(self, problem: PROBLEM) -> Optional[Dict[str, JSONABLE]]:
		"""
		(optional) Returns additional information about the problem to help the LLM solve it.

		:param problem: an *internal* representation of a specific problem
		"""
		pass



class Subject(AbstractSubject):
	pass



class ProtocolBase(AbstractProtocol):
	def __init__(self, *, seed: Optional[int] = None, name: str = '{task.name}_{subject.name}_{now:%Y-%m-%d_%H-%M-%S}',
				 **kwargs):
		if seed is None:
			seed = random.randint(0, 2**31 - 1)
		super().__init__(**kwargs)
		self._name_template = name
		self._name = None
		self._seed = seed
		self._now = datetime.now()

		self.task = None
		self.subject = None

	@property
	def name(self) -> str:
		return self._name


