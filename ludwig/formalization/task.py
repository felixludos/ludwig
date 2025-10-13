import json

from ..imports import *
from ..base import TaskBase, JudgedTask
from ..util import repo_root, AbstractFormalizer, PromptTemplate
from ..util.prompts import Custom_Formalizer


@fig.component('formalization')
class FormalizationTask(JudgedTask):
	def __init__(self, source: TaskBase, rep: Union[AbstractFormalizer, str] = None, **kwargs):
		if isinstance(rep, str):
			rep = rep.split('#')
			if len(rep) == 2 and rep[1].isdigit():
				rep[1] = int(rep[1])
			rep = Custom_Formalizer(*rep)
		super().__init__(**kwargs)
		self.source = source
		self.rep = rep

	@property
	def name(self) -> str:
		return f"Formalize-{self.source.name}"
	
	def json(self) -> JSONOBJ:
		return {'source': self.source.json(), 
		  		'rep': self.rep.json()}

	def prepare(self, seed: int = None) -> None:
		super().prepare()
		self.source.prepare()
		if self.rep is None:
			self.rep = self.source.formalizer()
		self.rep.prepare(self.source)

	def show_keys(self) -> Iterator[str]:
		yield 'observation'
		yield 'question'
		yield 'observation'
		yield 'schema'
		yield 'system'
		yield 'task'

	def store_keys(self) -> Iterator[str]:
		yield 'problem'
		yield 'question'
		yield 'answer'

	def context(self) -> str:
		return self.source.context()
		return f'This is an autoformalization task for:\n{self.source.context()}'

	def description(self) -> str:
		return self.source.description()
		return (f'Your task is to formalize a specific problem using a specific representation '
				f'given as a JSON schema to make progress towards the overall goal.')

	def specification(self) -> JSONOBJ:
		return {'schema': self.rep.schema()}
	
	@property
	def total_questions(self) -> Optional[int]:
		return self.source.total_questions

	def ask(self, index: int) -> JSONOBJ:
		ctx = self.source.ask(index)

		observation = ctx.get('observation')
		assert observation is not None, f'No obs found'
		question = ctx.get('question')
		assert question is not None, f'No question found'

		schema = self.rep.schema()
		answer = self.rep.formalize(ctx)

		return {
			'source': ctx,
			'problem': ctx.get('problem'),
			'question': question,
			'observation': observation,
			'answer': answer,
			'schema': schema,
			'system': self.context(),
			'task': self.description(),
		}
	
	def interpret(self, problem: JSONOBJ, response: JSONOBJ):

		raw = response['final']

		try:
			formal = json.loads(raw)
		except json.JSONDecodeError:
			formal = None

		return {'formal': formal, 'diffs': None if formal is None else self.rep.compare(problem['source'], formal)}
	
	def judge(self, problem: JSONOBJ, response: JSONOBJ) -> bool:
		return self.rep.correct(problem['source'], response['formal'])




	

	
