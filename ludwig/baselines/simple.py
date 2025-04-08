from .imports import *



@fig.component('direct-prompting')
class DirectPrompting(StrategyBase):
	"""
	Direct prompting strategy.
	"""

	def __init__(self, template: str = '{task_context}\n\n{question}', **kwargs):
		super().__init__(**kwargs)
		self.template = template
		self.system_context = None
		self.task_context = None


	@property
	def name(self):
		return 'direct-prompting'


	def json(self):
		return {
			'template': self.template,
		**super().json()}


	def study(self, context: str, desc: str, spec: JSONOBJ) -> Optional[JSONABLE]:
		self.system_context = context
		self.task_context = desc


	def solve(self, question: str, *, seed: Optional[int] = None,
			  side_information: Optional[JSONOBJ] = None) -> Tuple[str, JSONOBJ]:

		prompt = self.template.format(
			system_context=self.system_context,
			task_context=self.task_context,
			question=question
		)

		response = self.client.get_response(prompt)

		return response, {'prompt': prompt}



