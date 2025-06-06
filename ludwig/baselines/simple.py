from .imports import *



@fig.component('direct-prompting')
class DirectPrompting(ClientStrategy):
	"""
	Direct prompting strategy.
	"""

	def __init__(self, template: Union[PromptTemplate, str] = '{task_context}\n\n{question}',
				 params: Optional[JSONOBJ] = None, **kwargs):
		if not isinstance(template, PromptTemplate):
			template = PromptTemplate(template)
		if params is None:
			params = {}
		super().__init__(**kwargs)
		self.template = template
		self.params = params
		self.system_context = None
		self.task_context = None


	@property
	def name(self) -> str:
		return f'dp-{self.template.ident}'


	def json(self) -> JSONOBJ:
		return {'template': self.template.json(), **super().json()}


	def study(self, context: str, desc: str, spec: JSONOBJ) -> Optional[JSONDATA]:
		self.system_context = context
		self.task_context = desc


	def solve(self, question: str, *, side_information: Optional[JSONOBJ] = None) -> Tuple[str, JSONOBJ]:

		prompt = self.template.fill(
			system_context=self.system_context,
			task_context=self.task_context,
			question=question
		)

		response = self.client.get_response(prompt, **self.params)

		return response, {'prompt': prompt}



