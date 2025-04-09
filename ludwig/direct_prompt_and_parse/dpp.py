from .imports import *


@fig.component('direct-prompting')
class DirectPromptingPlusParse(StrategyBase):
	"""
	Direct prompting strategy.
	"""

	def __init__(self, client: AbstractClient, st_template:str,
				 init_state_est_template: str, info_extractor_template:str, state_desc_template:str,
				 response_template:str, **kwargs):
		super().__init__(**kwargs)
		self.client = client
		self.state_desc_template=state_desc_template
		self.state_transition_template = st_template
		self.response_template = response_template
		self.system_context = None
		self.task_context = None
		self.nl_description_state_transition = None
		self.max_iterations = 10
		self.init_state_est_prompt = init_state_est_template
		self.nl_info_extractor_prompt = info_extractor_template
		self.name_space = {}
		self.trajectory = []


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
		"""Extract the python implementation of state transition function given an LLM response"""
		raise NotImplementedError('Base class implementation called please override this function')

	def parse_info_extractor_function(self, desc_g) -> str:
		"""Extract the python implementation of information extractor function g"""
		raise NotImplementedError('Base class implementation called please override this function')

	def parse_state(self, desc_x:str) -> str:
		raise NotImplementedError('Base class implementation called please override this function')

	def choose_to_expand(self, x_js):
		""" implement BFS or DFS or some sort of heuristic supported search algo
		This is the \mathcal{C} function"""
		raise NotImplementedError('Base class implementation called please override this function')

	def get_state_transition(self):
		prompt = self.state_transition_template.format(c_sys=self.system_context)
		self.nl_description_state_transition = self.client.get_response(prompt)
		f = self.parse_state_transition_function(self.nl_description_state_transition)
		exec(f, self.namespace)

	def get_info_extractor(self, desc_x, c_task, c_query):
		prompt = self.nl_info_extractor_prompt.format(
			desc_x=desc_x,
			c_task=c_task,
			c_query=c_query
		)
		nl_info_extractor = self.client.get_response(prompt)
		g = self.parse_info_extractor_function(nl_info_extractor)
		exec(g, self.namespace)

	def initialize_search(self, start_node):
		"""
        Set the start node and prepare to begin searching.
        """
		raise NotImplementedError('Base class implementation called please override this function')

	def solve(self, question: str, *, seed: Optional[int] = None,
			  side_information: Optional[JSONOBJ] = None) -> str:

		self.get_state_transition()
		state_desc_prompt = self.state_desc_template.format(
			desc_f=self.nl_description_state_transition,
			c_sys=self.system_context
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
		self.initialize_search(x_i)
		for iter in range(self.max_iterations):
			x_js = self.namespace['expand'](x_i)
			y_i = self.namespace['evaluate'](self.trajectory)
			if y_i is None:
				break
			x_i = self.choose_to_expand(x_js) # return None if the search has finished
			if x_i is None:
				break

		response_prompt = self.response_template.format(
			c_task=self.task_context,
			c_query=question,
			trajectory=self.trajectory
		)
		response = self.client.get_response(response_prompt)
		return response
