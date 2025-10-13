from .imports import *


@fig.component('formalizer')
class FormalizerStrategy(ClientStrategy):
	def __init__(self, template: Union[PromptTemplate, str] = 'formalization-default', **kwargs):
		if template is None:
			template = PromptTemplate(template)
		super().__init__(**kwargs)
		self.template = template
		raise NotImplementedError('use standard zshot instead')

	@property
	def name(self) -> str:
		return self.template.ident

	def prepare(self, task: AbstractTask, judge: Optional[AbstractJudge] = None) -> Any:
		super().prepare(task, judge)

	def solve(self, problem: JSONOBJ) -> JSONOBJ:
		# assert 'question' in problem, 'Problem must contain a question'
		# question = problem['question']
		for key in self.template.variables():
			if key not in problem:
				print(f'WARNING: Template expects a "{key}" not found in problem. Error is probably imminent.')

		prompt = self.template.fill(**problem)

		# response = self.client.get_response(prompt, **self.params)
		resp = self.client.step(prompt, **self.params)

		response = self.client.extract_response(resp)

		return {'prompt': prompt, 'final': response}


	def json(self) -> JSONOBJ:
		return {'template': self.template.json(), **super().json()}




