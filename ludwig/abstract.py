from .imports import *
from .errors import ToolError, OptionalMethodNotImplemented, AmbiguousFormalizationError

PROBLEM = JSONABLE
ANSWER = JSONABLE
DECISION = JSONABLE


class AbstractTool:
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

	def json(self) -> JSONOBJ:
		raise NotImplementedError

	def schema(self, style: str = None) -> JSONOBJ:
		"""
		(optional) Returns the schema of the tool to be sent to the client.
		"""
		raise OptionalMethodNotImplemented

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

	def call(self, arguments: JSONABLE, *, seed: Optional[int] = None) -> str:
		"""
		Calls the tool with the given arguments and returns the result as a string.

		:param arguments: should adhere to the expected input specification. If not, will raise a `ToolError`.
		:param seed: optional to ensure deterministic behavior
		:raises: ToolError
		"""
		raise NotImplementedError



class AbstractTask:
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

	def validation(self, N: int, *, seed: Optional[int] = None) -> Iterator[Tuple[PROBLEM, ANSWER]]:
		"""
		(optional) Generates `N` pairs of input and expected output for the strategy to self-validate its formal system.

		This can also be used for a few-shot setting.

		:param seed: optional to ensure deterministic behavior
		"""
		raise OptionalMethodNotImplemented

	def prepare(self, seed: int) -> None:
		"""
		(optional) Setup any necessary state for this task

		This is called before the task is used, and can be used to initialize any state or configuration.

		:param seed: optional to ensure deterministic behavior
		"""
		pass

	def search_mode(self) -> JSONOBJ:
		"""
		(optional) Returns the suggested (or optimal) settings for the search to be relevant for this task.

		These settings may include information like whether the search should be DFS or BFS, which it should evaluate
		full roll-outs or states independently, etc.
		"""
		raise OptionalMethodNotImplemented

	def description(self) -> str:
		"""Task context including all the relevant details for the strategy about what this task is about"""
		raise NotImplementedError
	
	def specification(self) -> JSONOBJ:
		"""
		(optional) Returns the specification of the task, including all the relevant details for the strategy about what
		this task is about.

		This may include information like the input and output formats, and any other relevant details.
		"""
		raise OptionalMethodNotImplemented

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

	def side_information(self, problem: PROBLEM) -> Optional[JSONOBJ]:
		"""
		(optional) Returns additional information about the problem to help the strategy solve it.

		The information provided here should not be *necessary* to solve the problem, instead this may include
		mildly informative annotations or classifications to simplify the reasoning process.

		:param problem: an *internal* representation of a specific problem
		"""
		pass

	def observe(self, problem: PROBLEM, *, seed: int = None) -> str:
		"""
		Verbalizes a specific problem for the strategy, which defines the query context.

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

		:param response: the strategy's response to the observation of the of problem that `answer` solves
		:param answer: ground truth answer
		"""
		raise OptionalMethodNotImplemented

	def act(self, problem: PROBLEM, action: ANSWER, info: Optional[JSONOBJ] = None) -> Optional[JSONOBJ]:
		"""
		(optional) For interactive tasks, this method allows the strategy to act on the problem and response.
		"""
		raise OptionalMethodNotImplemented


	def correct(self, response: str, answer: ANSWER) -> Tuple[bool, JSONOBJ]:
		"""
		Returns whether the strategy's response is satisfactory and should be evaluated as correct.

		:param response: the strategy's response to the observation of the of problem that `answer` solves
		:param answer: ground truth answer
		"""
		raise NotImplementedError

	def validate_judge(self, judge: 'AbstractJudge') -> bool:
		"""
		(optional) Validates the given judge for this task

		This should return True if the judge is appropriate for the task and can be used to evaluate the response.
		"""
		raise OptionalMethodNotImplemented

	def present(self) -> Any:
		"""(optional) Returns any description or information for the strategy"""
		raise OptionalMethodNotImplemented

	def status(self) -> Optional[JSONOBJ]:
		"""
		(optional) Returns the current status of the strategy

		This may be called at any time, and should report the current state of the strategy.
		"""
		raise OptionalMethodNotImplemented

	def json(self) -> JSONOBJ:
		"""
		(optional) Returns the settings for the task to be relevant for this task.

		These settings should generally include all important hyperparameters and configuration settings for the task.
		Also, it is recommended to format them such that they can be published on wandb.
		"""
		raise OptionalMethodNotImplemented

	def checkpoint(self, path: Optional[Path] = None) -> Optional[JSONOBJ]:
		"""
		(optional) Returns a checkpoint of the task state or saves the checkpoint to the given path.

		When a path is provided, the checkpoint should be saved to that path. Otherwise, it should return a dictionary
		with all the relevant information to restore the task state.
		"""
		raise OptionalMethodNotImplemented

	def load_checkpoint(self, *, path: Optional[Path] = None, data: Optional[JSONOBJ] = None) -> None:
		"""
		(optional) Loads the checkpoint from the given path or data.

		If a path is provided, the checkpoint should be loaded from that path. Otherwise, it should load the state from
		the given data.
		"""
		raise OptionalMethodNotImplemented



class AbstractStrategy:
	@property
	def name(self) -> str:
		"""A unique and description name for this strategy"""
		raise NotImplementedError

	@property
	def model_name(self) -> str:
		"""A unique and description name for this strategy"""
		raise NotImplementedError

	def prepare(self, seed: int) -> None:
		"""
		(optional) Setup any necessary state for this strategy

		This is called before the strategy is used, and can be used to initialize any state or configuration.

		:param seed: optional to ensure deterministic behavior
		"""
		raise NotImplementedError

	def solve(self, question: str, *, side_information: Optional[JSONOBJ] = None) -> Tuple[str, JSONOBJ]:
		"""
		Use strategy to find a solution to the given question

		Additionally, returns any intermediate steps that are worth recording for logging.

		:param question: the question to respond to
		:param seed: optional to ensure deterministic behavior
		:param side_information: optional additional information to help the strategy solve the question
		"""
		raise NotImplementedError

	def study(self, context: str, task_description: str, task_spec: JSONOBJ) -> Optional[JSONABLE]:
		"""
		(optional) Processes the given system and task context to prepare for a specific task

		:param context: the system context for this task
		:param task_description: the task context
		"""
		pass

	def status(self) -> Optional[JSONOBJ]:
		"""
		(optional) Returns the current status of the strategy

		This may be called at any time, and should report the current state of the strategy.
		"""
		raise OptionalMethodNotImplemented

	def collect_stats(self) -> ContextManager:
		raise OptionalMethodNotImplemented

	def json(self) -> JSONOBJ:
		"""
		(optional) Returns the settings for the strategy to be relevant for this strategy.

		These settings should generally include all important hyperparameters and configuration for the strategy.
		Also, it is recommended to format them such that they can be published on wandb.
		"""
		raise OptionalMethodNotImplemented

	def checkpoint(self, path: Optional[Path] = None) -> Optional[JSONOBJ]:
		"""
		(optional) Returns a checkpoint of the strategy state or saves the checkpoint to the given path.

		When a path is provided, the checkpoint should be saved to that path. Otherwise, it should return a dictionary
		with all the relevant information to restore the strategy state.
		"""
		raise OptionalMethodNotImplemented

	def load_checkpoint(self, *, path: Optional[Path] = None, data: Optional[JSONOBJ] = None) -> None:
		"""
		(optional) Loads the checkpoint from the given path or data.

		If a path is provided, the checkpoint should be loaded from that path. Otherwise, it should load the state from
		the given data.
		"""
		raise OptionalMethodNotImplemented



class AbstractJudge:
	"""
	Judges are used by protocols to interpret the response of the strategy and determine whether it is correct or not.
	"""
	@property
	def name(self) -> str:
		"""A unique and description name for this judge"""
		raise NotImplementedError

	def format_description(self, task_description: str) -> str:
		"""
		(optional) Format the task description for the strategy so the judge can understand responses better.

		For example, the judge may request the answers to be formated in a specific way.
		"""
		raise OptionalMethodNotImplemented

	def interpret(self, question: str, response: str) -> Tuple[DECISION, Optional[JSONOBJ]]:
		"""
		(optional) Interprets the response of the strategy and returns a decision and any additional information.

		This is used to help the judge understand the response better, and may include information like the
		intermediate steps taken to reach the answer.
		"""
		raise OptionalMethodNotImplemented

	def judge(self, decision: DECISION, answer: JSONABLE, info: Optional[JSONOBJ] = None) -> bool:
		raise NotImplementedError

	def prepare(self, task_spec: JSONOBJ) -> None:
		raise NotImplementedError

	def collect_stats(self) -> ContextManager:
		raise OptionalMethodNotImplemented

	def status(self) -> Optional[JSONOBJ]:
		"""
		(optional) Returns the current status of the judge

		This may be called at any time, and should report the current state of the judge.
		"""
		raise OptionalMethodNotImplemented

	def json(self) -> JSONOBJ:
		"""
		(optional) Returns the settings for the judge to be relevant for this judge.

		These settings should generally include all important hyperparameters and configuration for the judge.
		Also, it is recommended to format them such that they can be published on wandb.
		"""
		raise OptionalMethodNotImplemented




class AbstractProtocol:
	def prepare(self) -> Optional[JSONOBJ]:
		"""(optional) Prepare all the necessary state for this protocol"""
		raise OptionalMethodNotImplemented

	def remaining_iterations(self) -> range:
		"""(optional) Returns the number of iterations remaining in this protocol"""
		raise OptionalMethodNotImplemented

	@property
	def name(self):
		"""
		Name of this experiment, should be unique
		
		Used to create a folder with the outputs
		"""
		raise NotImplementedError

	@property
	def task(self) -> AbstractTask:
		"""The task used in this protocol"""
		raise NotImplementedError

	def pre_loop(self) -> Optional[JSONOBJ]:
		"""Called before loop to setup any metrics"""
		raise NotImplementedError

	def describe(self) -> Optional[str]:
		"""Report setup to stdout before starting the experiment"""
		raise OptionalMethodNotImplemented

	def step(self, index: int) -> JSONOBJ:
		"""Called every iteration"""
		raise NotImplementedError

	def status(self) -> JSONOBJ:
		"""
		(optional) Report the current status of the protocol

		This may be called at any time, and should report the current state of the protocol.
		"""
		raise OptionalMethodNotImplemented

	def summary(self) -> str:
		"""
		Report summary statistics and results (so far)
		
		This may be called before the end of the experiment, so it should report metrics so far
		"""
		raise OptionalMethodNotImplemented

	def post_loop(self) -> Optional[JSONOBJ]:
		"""Clean up and return final results as a JSON object"""
		raise NotImplementedError

	def json(self) -> JSONOBJ:
		"""
		(optional) Returns the settings for the protocol to be relevant for this protocol.

		These settings should generally include all important hyperparameters and configuration for the protocol.
		Also, it is recommended to format them such that they can be published on wandb.
		"""
		raise OptionalMethodNotImplemented

	def checkpoint(self, path: Optional[Path] = None) -> Optional[JSONOBJ]:
		"""
		(optional) Returns a checkpoint of the protocol state or saves the checkpoint to the given path.

		When a path is provided, the checkpoint should be saved to that path. Otherwise, it should return a dictionary
		with all the relevant information to restore the protocol state.
		"""
		raise OptionalMethodNotImplemented

	def load_checkpoint(self, *, path: Optional[Path] = None, data: Optional[JSONOBJ] = None) -> None:
		"""
		(optional) Loads the checkpoint from the given path or data.

		If a path is provided, the checkpoint should be loaded from that path. Otherwise, it should load the state from
		the given data.
		"""
		raise OptionalMethodNotImplemented




