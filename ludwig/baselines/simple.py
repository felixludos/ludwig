from .imports import *



@fig.component('direct-prompting')
class DirectPrompting(StrategyBase):
	"""
	Direct prompting strategy.
	"""

	def __init__(self, template: Union[PromptTemplate, str] = '{task_context}\n\n{question}', **kwargs):
		if not isinstance(template, PromptTemplate):
			template = PromptTemplate(template)
		super().__init__(**kwargs)
		self.template = template
		self.system_context = None
		self.task_context = None


	@property
	def name(self) -> str:
		return f'direct-prompting-{self.template.ident}'


	def json(self) -> JSONOBJ:
		return {'template': self.template.json(), **super().json()}


	def study(self, context: str, desc: str, spec: JSONOBJ) -> Optional[JSONABLE]:
		self.system_context = context
		self.task_context = desc


	def _solve(self, question: str, *, seed: Optional[int] = None,
			   side_information: Optional[JSONOBJ] = None) -> Tuple[str, JSONOBJ]:

		prompt = self.template.fill(
			system_context=self.system_context,
			task_context=self.task_context,
			question=question
		)

		response = self.client.get_response(prompt)

		return response, {'prompt': prompt}



