from .imports import *
from ..util import PromptTemplate, PythonParser, AbstractCoder, AbstractSearch, hash_str
from ..util.search import GenericSearch
from ..errors import ExceededRetriesError


@fig.component('dpp')
class DirectPromptingPlusParse(ClientStrategy):
	"""
	Direct prompting strategy.
	"""
	def __init__(self, *, parser: AbstractCoder = None, searcher: Optional[AbstractSearch] = None,
				 expand_template: str = 'dpp/expand-fn', extract_template: str = 'dpp/extract-fn',
				 representation_template: str = 'dpp/design-rep', select_template: Optional[str] = None,# 'dpp/select-fn',
				 state_estimation_template: str = 'dpp/state-estimation', response_template: str = 'dpp/response',
				 retry_error_template: str = 'dpp/retry-error', retry_missing_template: str = 'dpp/retry-missing',
				 examples_template: str = 'dpp/examples', max_retries: int = 3, num_validation: int = 3, **kwargs):
		if parser is None:
			parser = PythonParser()
		if searcher is None:
			searcher = GenericSearch(markovian=True)
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
		if not isinstance(retry_error_template, PromptTemplate):
			retry_error_template = PromptTemplate(retry_error_template)
		if not isinstance(retry_missing_template, PromptTemplate):
			retry_missing_template = PromptTemplate(retry_missing_template)
		if not isinstance(examples_template, PromptTemplate):
			examples_template = PromptTemplate(examples_template)
		super().__init__(**kwargs)
		self.parser = parser
		self.searcher = searcher
		self.max_retries = max_retries
		self.num_validation = num_validation
		self.representation = None
		self.expand_code = None
		self.expand_fn = None

		self.expand_template = expand_template
		self.extract_template = extract_template
		self.representation_template = representation_template
		self.select_template = select_template
		self.state_estimation_template = state_estimation_template
		self.response_template = response_template
		self.retry_error_template = retry_error_template
		self.retry_missing_template = retry_missing_template
		self.examples_template = examples_template
		self._template_code = hash_str(''.join([
			self.expand_template.code,
			self.extract_template.code,
			self.representation_template.code,
			self.select_template.code if self.select_template else '',
			self.state_estimation_template.code,
			self.response_template.code,
			self.retry_error_template.code,
			self.retry_missing_template.code,
			self.examples_template.code,
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
			'retry_error_template': self.retry_error_template.json(),
			'retry_missing_template': self.retry_missing_template.json(),
			'examples_template': self.examples_template.json(),
			'max_retries': self.max_retries,
			**super().json()
		}

	def _checkpoint_data(self) -> JSONOBJ:
		return {
			'expand_code': self.expand_code,
			'code': self._template_code,
			'examples': self.examples,
			'representation': self.representation,
			**super()._checkpoint_data()
		}

	def _load_checkpoint_data(self, checkpoint_data: JSONOBJ, *, unsafe: bool = False) -> None:
		super()._load_checkpoint_data(checkpoint_data)
		self.expand_code = checkpoint_data['expand_code']
		if self.expand_code is not None:
			self.expand_fn = self.parser.realize(self.expand_code)['local_vars']['expand']
		self.representation = checkpoint_data['representation']

	def _find_py_obj(self, prompt: str, target: str = None) -> Tuple[str, int, Dict[str, Any]]:
		retries = 0
		chat = self.client.begin_chat(prompt)
		for resp in self.client.multi_turn(chat, max_retries=self.max_retries):
			response = self.client.extract_response(resp)

			code_blocks = self.parser.parse(response)

			for i, code in enumerate(code_blocks):
				item = self.parser.realize(code)

				if (target is None and len(item.get('local_vars', []))) or (target in item.get('local_vars', {})):
					if target is not None and callable(item['local_vars'].get(target)):
						item['local_vars'][target].__globals__.update(item['local_vars'])
					return response, retries, item
				elif i+1 == len(code_blocks):
					template = self.retry_error_template if 'error' in item else self.retry_missing_template
					chat.append({'role': 'user', 'content': template.fill(target=target, **item)})

			retries += 1

		raise ExceededRetriesError(f'{target}')

	def _validate_fn(self, fn: Callable, num: int, content: Dict[str, Any]):
		missing = 0
		failed = []
		for i in range(num):
			inkey, outkey = f'input_state{i+1}', f'output_state{i+1}'
			if inkey in content and outkey in content:
				inp, out = content[inkey], content[outkey]
				try:
					if fn(inp) != out:
						failed.append((inp, out, None))
				except Exception as e:
					failed.append((inp, out, e))
			else:
				missing += 1

		return missing, failed

	def study(self, context: str, desc: str, spec: JSONOBJ) -> JSONOBJ:
		self.task_context = desc
		self.system_context = context

		expand_prompt, expand_response = None, None
		expand_retries = None
		if self.expand_code is None:
			expand_prompt = self.expand_template.fill(
				c_sys=context,
				c_task=desc
			)
			expand_response, expand_retries, expand_item = self._find_py_obj(expand_prompt, 'expand')
			self.expand_fn = expand_item['local_vars']['expand']
			self.expand_code = expand_item['code']

		elif self.expand_fn is None:
			assert self.expand_code is not None, 'expand_code must be set if expand_fn is not None'
			self.expand_fn = self.parser.realize(self.expand_code)['local_vars']['expand']

		rep_prompt = None
		if self.representation is None:
			rep_prompt = self.representation_template.fill(
				expand_prompt=expand_prompt,
				expand_response=expand_response,
				expand_code=self.expand_code,
				c_sys=context,
				c_task=desc
			)
			self.representation = self.client.get_response(rep_prompt)

		examples_prompt = self.examples_template.fill(
			c_sys=context,
			c_task=desc,
			num=self.num_validation,
			target='expand',
			representation=self.representation,
			code=self.expand_code,
		)
		examples_response, examples_retries, examples_item = self._find_py_obj(examples_prompt,
																			   f'output_state{self.num_validation}')

		examples_missing, examples_failed = self._validate_fn(self.expand_fn, self.num_validation, examples_item)

		return {
			'expand_prompt': expand_prompt,
			'expand_response': expand_response,
			'expand_code': self.expand_code,
			'expand_retries': expand_retries,
			'representation_prompt': rep_prompt,
			'representation_response': self.representation,
			'examples_prompt': examples_prompt,
			'examples_response': examples_response,
			'examples_code': examples_item['code'],
			'examples_retries': examples_retries,
		}

	def solve(self, question: str, *, side_information: Optional[JSONOBJ] = None) -> Tuple[str, JSONOBJ]:

		state_prompt = self.state_estimation_template.fill(
			c_sys=self.system_context,
			c_task=self.task_context,
			desc_x=self.representation,
			c_query=question,
		)
		state_response, state_retries, state_item = self._find_py_obj(state_prompt, 'state')
		state = state_item['local_vars']['state']
		state_code = state_item['code']

		extract_prompt = self.extract_template.fill(
			c_sys=self.system_context,
			c_task=self.task_context,
			desc_x=self.representation,
			c_query=question,
		)
		extract_response, extract_retries, extract_item = self._find_py_obj(extract_prompt, 'extract')
		extract_fn = extract_item['local_vars']['extract']
		extract_code = extract_item['code']

		try:
			ex_out = self.expand_fn(state)
		except:
			print(f'state: {state}')
			print('**'*20)
			print(self.expand_code)
			print('**'*20)
			print(extract_code)
			print('**'*20)
			raise

		try:
			ev_out = extract_fn([state])
		except:
			print(f'state: {state}')
			print('**'*20)
			print(self.expand_code)
			print('**'*20)
			print(extract_code)
			print('**'*20)
			raise

		results = list(self.searcher.run(state, expand_fn=self.expand_fn, extract_fn=extract_fn))
		report = '\n'.join(results)

		response_prompt = self.response_template.fill(
			c_task=self.task_context,
			c_query=question,
			report=report,
		)
		response = self.client.get_response(response_prompt)

		return response, {
			'state_prompt': state_prompt,
			'state_response': state_response,
			'state_code': state_code,
			'state_retries': state_retries,

			'extract_prompt': extract_prompt,
			'extract_response': extract_response,
			'extract_code': extract_code,
			'extract_retries': extract_retries,

			'report': report,
			'response_prompt': response_prompt,
		}
