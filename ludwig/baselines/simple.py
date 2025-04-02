from .imports import *



@fig.component('direct-prompting')
class DirectPrompting(Strategy):
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

		# TODO: Use the prompt to generate a response
		response = 'Yes'

		return response



