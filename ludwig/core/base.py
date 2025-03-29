from .imports import *
from .errors import ToolError, OptionalMethodNotImplemented, AmbiguousFormalizationError


PROBLEM = JSONABLE
ANSWER = JSONABLE



class LLM_Tool:
	@property
	def name(self) -> str:
		"""A descriptive and ideally unique name for this tool"""
		raise NotImplementedError

	def short_description(self) -> str:
		"""
		(optional) A one-line description of this tool

		Intended to be used for a description of this tool in a list of *many* available potentially useful tools.
		"""
		raise OptionalMethodNotImplemented

	def description(self) -> str:
		"""
		Detailed description of what this tool does and how to call it.

		The desciption may include example inputs and outputs, and should provide enough information to help identify
		under what circumstances the tool is useful, how to effectively use the tool, and what results to expect.
		"""
		raise NotImplementedError

	def describe_representation(self) -> str:
		"""
		(optional) Description of the input specification to successfully run this tool.

		Could be a json schema, possibly including examples.
		"""
		raise OptionalMethodNotImplemented

	def formalize(self, problem: PROBLEM) -> str:
		"""
		(optional) Converts the *internal* representation of a specific problem into the format this tool requires

		If the given problem does not have an unambiguously correct application of this tool, this should throw a
		`AmbiguousFormalizationError` error. This method is primarily used for automatically generated explanations,
		and for testing.

		:param problem: task-specific representation
		:raises: AmbiguousFormalizationError
		"""
		raise OptionalMethodNotImplemented

	def call(self, arguments: str, *, seed: Optional[int] = None) -> str:
		"""
		Calls the tool with the given arguments and returns the result as a string.

		:param arguments: should adhere to the expected input specification. If not, will raise a `ToolError`.
		:param seed: optional to ensure deterministic behavior
		:raises: ToolError
		"""
		raise NotImplementedError




class Task:
	@property
	def name(self) -> str:
		"""A unique and description name for this task"""
		raise NotImplementedError

	@property
	def total_questions(self) -> Optional[int]:
		"""
		Returns the total number of questions this task has (if this is pre-defined)

		This is especially useful for questions which are loaded from an existing dataset. If so, then the `load` method
		will be used instead of the `generate`. If the questions can be generated on the fly or there is some large
		number of options, then this can return `None`.
		"""
		raise NotImplementedError

	def context(self) -> str:
		"""
		Returns the system context for this task

		Including all the information potentially useful to construct a formal system which can help solve the task.
		Ultimately, this should return a string to feed directly to a
		"""
		raise NotImplementedError

	def validation(self, n: int, *, seed: Optional[int] = None) -> Iterator[Tuple[str, str]]:
		"""
		(optional) Generates `n` pairs of input and expected output for the LLM to self-validate its formal system.

		:param seed: optional to ensure deterministic behavior
		"""
		raise OptionalMethodNotImplemented

	def search_mode(self) -> Dict[str, JSONABLE]:
		"""
		(optional) Returns the suggested (or optimal) settings for the search to be relevant for this task.

		These settings may include information like whether the search should be DFS or BFS, which it should evaluate
		full roll-outs or states independently, etc.
		"""
		raise OptionalMethodNotImplemented

	def description(self) -> str:
		"""Task context including all the relevant details for the LLM about what this task is about"""
		raise NotImplementedError

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

	def load(self, index: int, *, seed: Optional[int] = None) -> Tuple[PROBLEM, ANSWER]:
		"""
		Loads the question and associated ground-truth answer corresponding to the given `index`.

		A pre-condition for this method to be used is that `self.total_questions` is not `None`

		:param index: 0 <= `index` < `self.total_questions`
		:param seed: optional to ensure deterministic behavior
		"""
		raise NotImplementedError

	def observe(self, problem: PROBLEM, *, seed: int = None) -> str:
		"""
		Verbalizes a specific problem for the LLM, which defines the query context.

		:param problem: an *internal* representation of a specific problem
		:param seed: optional to ensure deterministic behavior
		"""
		raise NotImplementedError

	def rationale(self, problem: PROBLEM, answer: ANSWER, *, seed: int = None) -> Iterator[str]:
		"""
		(optional) Step-by-step walk through of the problem to reach the answer

		:param problem: an *internal* representation of a specific question
		:param answer: ground truth answer
		:param seed: optional to ensure deterministic behavior
		"""
		raise OptionalMethodNotImplemented

	def explanation(self, problem: PROBLEM, answer: ANSWER, *, seed: int = None) -> str:
		"""
		(optional) Detailed explanation of how to solve the given `problem` to reach `answer`

		Unlike `self.rationale`, this method doesn't break the explanation into individual steps, and instead just
		explains the solution. This can to some extent be treated as a summary of the rationale.

		:param problem: an *internal* representation of a specific question
		:param answer: ground truth answer
		:param seed: optional to ensure deterministic behavior
		"""
		raise OptionalMethodNotImplemented

	def score(self, response: str, answer: ANSWER) -> float:
		"""
		(optional) Returns a numeric score for the correctness of the given `response` for deeper evaluation.

		:param response: the LLM's response to the observation of the of problem that `answer` solves
		:param answer: ground truth answer
		"""
		raise OptionalMethodNotImplemented

	def correct(self, response: str, answer: ANSWER) -> bool:
		"""
		Returns whether the LLM's response is satisfactory and should be evaluated as correct.

		:param response: the LLM's response to the observation of the of problem that `answer` solves'
		:param answer: ground truth answer
		"""
		raise NotImplementedError

	def best_tool(self) -> LLM_Tool:
		"""(optional) Returns the most relevant tool to solve this task."""
		raise OptionalMethodNotImplemented

	def relevant_solvers(self) -> Iterable[LLM_Tool]:
		"""(optional) Returns a sequence of potentially or partially relevant tools that may help to solve this task."""
		raise OptionalMethodNotImplemented











