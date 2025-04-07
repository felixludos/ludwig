from .imports import *



@fig.component('direct-prompting')
class DirectPromptingPlusParse(StrategyBase):
	"""
	Direct prompting strategy.
	"""

	def __init__(self, client: AbstractClient, st_template:str,
				 init_state_est_prompt: str, info_extractor_prompt:str, **kwargs):
		super().__init__(**kwargs)
		self.client = client
		self.state_transition_template = st_template
		self.system_context = None
		self.task_context = None
		self.nl_description_state_transition = None
		self.max_iterations = 10
		self.init_state_est_prompt = init_state_est_prompt
		self.nl_info_extractor_prompt = info_extractor_prompt
		self.name_space = {}


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

	def parse_state_transition_function(self, desc_f) -> str:
		raise NotImplementedError('Base class implementation called please override this function')

	def parse_state(self, desc_x) -> str:
		raise NotImplementedError('Base class implementation called please override this function')

	def choose_to_expand(self, x_js):
		# implement BFS or DFS or some sort of heuristic supported search algo
		raise NotImplementedError('Base class implementation called please override this function')

	def get_response_prompt(self, c_task, c_query, trajectory):
		# Give  the task context, the question and the expanded trajectory formulate a prompt to answer the question
		raise NotImplementedError('Base class implementation called please override this function')

	def get_state_transition(self):
		prompt = self.state_transition_template.format(self.system_context)
		self.nl_description_state_transition = self.client.get_response(prompt)
		f = self.parse(self.nl_description_state_transition)
		exec(f, self.namespace)

	def get_info_extractor(self, desc_x, c_task, c_query):
		prompt = self.nl_info_extractor_prompt.format(
			desc_x=desc_x,
			c_task=self.task_context,
			c_query=c_query
		)
		nl_info_extractor = self.client.get_response(prompt)
		g = self.parse(nl_info_extractor)
		exec(g, self.namespace)


	def solve(self, question: str, *, seed: Optional[int] = None,
			  side_information: Optional[JSONOBJ] = None) -> str:

		self.get_state_transition()
		state_desc_prompt = self.state_desc_prompt.format(
			st_func_desc=self.nl_description_state_transition,
			system_context=self.system_context
		)
		desc_x = self.client.get_response(state_desc_prompt)

		if side_information and "max_iterations" in side_information:
			self.max_iterations = side_information["max_iterations"]

		# Handling only one question so no for loop
		initial_sate_est_prompt = self.init_state_est_prompt.format(
			desc_x = desc_x,
			c_task = self.task_context,
			c_query = question
		)
		x_i = self.parse_state(self.client.get_response(initial_sate_est_prompt))
		self.get_info_extractor(
			desc_x=desc_x,
			c_task=self.task_context,
			c_query=question
		)
		y = None
		trajectory = [x_i,]
		for iter in range(self.max_iterations):
			x_js = self.namespace['f'](x_i)
			y_i = self.namespace['g'](trajectory)
			x_i = self.choose_to_expand(x_js)
			trajectory.append(x_i)
			if y_i is None:
				break

		response_prompt_prompt = self.get_response_prompt(
			c_task=self.task_context,
			c_query=question,
			trajectory=trajectory
		)
		response = self.client.get_response(response_prompt_prompt)
		return response



