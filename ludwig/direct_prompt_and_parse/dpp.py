from .imports import *



@fig.component('direct-prompting')
class DirectPrompting(StrategyBase):
	"""
	Direct prompting strategy.
	"""

	def __init__(self, client: AbstractClient, template: str = '{task_context}\n\n{question}', **kwargs):
		super().__init__(**kwargs)
		self.client = client
		self.template = template
		self.system_context = None
		self.task_context = None


	def prepare(self, seed: Optional[int] = None) -> Any:
		"""Prepare the strategy for use. This may include setting up any necessary resources or configurations."""
		if not self.client.ping():
			raise ValueError(f'Client {self.client.ident} is not ready to use.')
		self.client.prepare()


	@property
	def name(self):
		return 'direct-prompting-plus-parse'


	def json(self):
		return {
			'template': self.template,
			'client': self.client.json(),
		**super().json()}


	def status(self) -> Optional[JSONOBJ]:
		return self.client.stats()


	def study(self, context: str, desc: str, spec: JSONOBJ) -> JSONOBJ:
		self.system_context = context
		self.task_context = desc
		return spec


	def solve(self, question: str, *, seed: Optional[int] = None,
			  side_information: Optional[JSONOBJ] = None) -> str:

		prompt = self.template.format(
			system_context=self.system_context,
			task_context=self.task_context,
			question=question
		)
        #TODO(Partha): On progress
		response = self.client.get_response(prompt)

		return response



