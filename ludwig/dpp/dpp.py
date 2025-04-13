from .imports import *
from ..util import PromptTemplate, PythonParser, AbstractParser, AbstractSearch, hash_str
from ..util.search import NaiveSearch


@fig.component('dpp')
class DirectPromptingPlusParse(StrategyBase):
	"""
	Direct prompting strategy.
	"""
	def __init__(self, *, parser: AbstractParser = None, searcher: Optional[AbstractSearch] = None,
				 expand_template: str = 'dpp/expand-fn', extract_template: str = 'dpp/extract-fn',
				 representation_template: str = 'dpp/design-rep', select_template: Optional[str] = None,# 'dpp/select-fn',
				 state_estimation_template: str = 'dpp/state-estimation', response_template: str = 'dpp/response',
				 **kwargs):
		if parser is None:
			parser = PythonParser()
		if searcher is None:
			searcher = NaiveSearch()
		if not isinstance(expand_template, PromptTemplate):
			expand_template = PromptTemplate(expand_template)
		if not isinstance(extract_template, PromptTemplate):
			extract_template = PromptTemplate(extract_template)
		if not isinstance(representation_template, PromptTemplate):
			representation_template = PromptTemplate(representation_template)
		if select_template is not None and not isinstance(select_template, PromptTemplate):
			select_template = PromptTemplate(select_template)
		if not isinstance(state_estimation_template, PromptTemplate):
			state_estimation_template = PromptTemplate(state_estimation_template)
		if not isinstance(response_template, PromptTemplate):
			response_template = PromptTemplate(response_template)
		super().__init__(**kwargs)
		self.parser = parser
		self.searcher = searcher
		self.namespace = {}
		self.representation = None
		self.blocks = None

		self.expand_template = expand_template
		self.extract_template = extract_template
		self.representation_template = representation_template
		self.select_template = select_template
		self.state_estimation_template = state_estimation_template
		self.response_template = response_template
		self._template_code = hash_str(''.join([
			self.expand_template.code,
			self.extract_template.code,
			self.representation_template.code,
			self.select_template.code if self.select_template else '',
			self.state_estimation_template.code,
			self.response_template.code
		]))

		self.system_context = None
		self.task_context = None
		self.nl_description_state_transition = None
		self.trajectory = []


	@property
	def name(self):
		return f'dpp-{self._template_code[:4]}'

	def prepare(self, seed: Optional[int] = None) -> Any:
		super().prepare(seed)
		self.parser.prepare()

	def json(self) -> JSONOBJ:
		return {
			'parser': self.parser.json(),
			'expand_template': self.expand_template.json(),
			'extract_template': self.extract_template.json(),
			'representation_template': self.representation_template.json(),
			'select_template': self.select_template.json() if self.select_template else None,
			'state_estimation_template': self.state_estimation_template.json(),
			'response_template': self.response_template.json(),
			**super().json()
		}

	def _checkpoint_data(self) -> JSONOBJ:
		return {
			'blocks': self.blocks,
			'code': self._template_code,
			'representation': self.representation,
			**super()._checkpoint_data()
		}

	def _load_checkpoint_data(self, checkpoint_data: JSONOBJ, *, unsafe: bool = False) -> None:
		super()._load_checkpoint_data(checkpoint_data)
		self.blocks = checkpoint_data['blocks']
		self.representation = checkpoint_data['representation']

	def study(self, context: str, desc: str, spec: JSONOBJ) -> JSONOBJ:
		expand_prompt = self.expand_template.fill(
			c_sys=context,
			c_task=desc
		)
		expand_response = self.client.get_response(expand_prompt)

		self.blocks = self.parser.parse(expand_response)
		self.namespace = self.parser.realize(self.blocks)

		rep_prompt = self.representation_template.fill(
			expand_prompt=expand_prompt,
			expand_response=expand_response,
			artifacts=self.blocks,
			c_sys=context,
			c_task=desc
		)
		self.representation = self.client.get_response(rep_prompt)

		return {
			'expand_prompt': expand_prompt,
			'expand_response': expand_response,
			'representation_prompt': rep_prompt,
			'representation_response': self.representation,
			'blocks': len(self.blocks),
		}

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
