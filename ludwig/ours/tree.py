from .imports import *
from .. import AbstractTask
from ..errors import BudgetExceededError
from ..util import StubTask, PromptTemplate, hash_str, extract_code_blocks
from ..abstract import AbstractJudge

# https://gemini.google.com/app/a7a756e8ae56a3cc

@fig.component('ours/tree-builder')
class TreeBuilder(ClientStrategy):
	def __init__(self, task: 'AbstractTask',
				 rep_template: Union[PromptTemplate, str] = 'tree/rep',

				 expand_template: Union[PromptTemplate, str] = 'tree/expand',
				 extract_template: Union[PromptTemplate, str] = 'tree/extract',
				 evaluate_template: Union[PromptTemplate, str] = 'tree/evaluate',

				 generate_template: Union[PromptTemplate, str] = 'perception/generate',
				 encode_template: Union[PromptTemplate, str] = 'tree/encode',

				 confirm_choice_template: Union[PromptTemplate, str] = 'confirm-choice',
				 safety_template: Union[PromptTemplate, str] = 'safe-code',
				 num_examples: int = 1, max_retries: int = 3, **kwargs):
		if not isinstance(rep_template, PromptTemplate):
			rep_template = PromptTemplate(rep_template)
		if not isinstance(expand_template, PromptTemplate):
			expand_template = PromptTemplate(expand_template)
		if not isinstance(extract_template, PromptTemplate):
			extract_template = PromptTemplate(extract_template)
		if not isinstance(evaluate_template, PromptTemplate):
			evaluate_template = PromptTemplate(evaluate_template)
		if not isinstance(generate_template, PromptTemplate):
			generate_template = PromptTemplate(generate_template)
		if not isinstance(encode_template, PromptTemplate):
			encode_template = PromptTemplate(encode_template)
		if not isinstance(confirm_choice_template, PromptTemplate):
			confirm_choice_template = PromptTemplate(confirm_choice_template)
		if not isinstance(safety_template, PromptTemplate):
			safety_template = PromptTemplate(safety_template)
		super().__init__(**kwargs)
		self.task = task
		self.rep_template = rep_template
		self.expand_template = expand_template
		self.extract_template = extract_template
		self.evaluate_template = evaluate_template
		self.generate_template = generate_template
		self.encode_template = encode_template
		self.confirm_choice_template = confirm_choice_template
		self.safety_template = safety_template
		self._template_code = hash_str(''.join([
			self.rep_template.code,
			self.expand_template.code,
			self.extract_template.code,
			self.evaluate_template.code,
			self.encode_template.code,
			self.confirm_choice_template.code,
			self.safety_template.code
		]))
		self.examples: Optional[List[JSONOBJ]] = None
		self.num_examples = num_examples
		self._max_retries = max_retries

	@property
	def name(self) -> str:
		return f'tree-build-{self.task.name}-{self._template_code[:4]}'

	def prepare(self, task: StubTask, judge: Optional[AbstractJudge] = None) -> Any:
		super().prepare(task, judge)
		self.task.prepare()
		if self.examples is None:
			self.examples = [self.task.ask_dev(i) for i in range(self.num_examples)]

	def json(self) -> JSONOBJ:
		return {
			'task': self.task.json(),

			'rep_template': self.rep_template.json(),
			'expand_template': self.expand_template.json(),
			'extract_template': self.extract_template.json(),
			'evaluate_template': self.evaluate_template.json(),
			'encode_template': self.encode_template.json(),
			'confirm_choice_template': self.confirm_choice_template.json(),
			'safety_template': self.safety_template.json(),

			'num_examples': self.num_examples,
			**super().json()
		}

	def solve(self, problem: JSONOBJ) -> JSONOBJ:
		ctx = {
			'task': self.task.description(),
			'context': self.task.context(),
			**problem
		}

		chat = self.client.begin_chat()
		self._create_representation(ctx, chat)

		self._implement_expand(ctx, chat)
		self._implement_extract(ctx, chat)
		self._implement_evaluate(ctx, chat)

		# try:
		# 	alts = self._generate_variations(5, self.examples[0], ctx, n_parallel=4)
		# except BudgetExceededError as e:
		# 	if e.resp is not None:
		# 		ctx['raw_alts'] = e.resp
		# 	print(f'Error generating variations: {e}')
		# else:
		# 	ctx['alts'] = alts
		#
		# 	formals = [self._formalize_state({'question': alt}, ctx['rep'], ctx, chat, max_tokens=1024,
		# 									 temperature=0.1)
		# 			   for alt in alts]
		#
		# 	ctx['formals'] = formals

		# self._test_implementations(ctx, chat)

		ctx['chat'] = chat
		return ctx

	def _create_representation(self, ctx: JSONOBJ, chat: List[Dict[str, JSONDATA]]) -> JSONDATA:
		prompt = self.rep_template.fill(**ctx, examples=self.examples)
		seed = ctx.get('seed', None)

		chat.append({'role': 'user', 'content': prompt})
		for resp in self.client.multi_turn(chat, dict(seed=seed), max_retries=self._max_retries):
			json_blocks = list(extract_code_blocks(chat[-1]['content'], 'json'))

			if len(json_blocks) == 0:
				chat.append({'role': 'user', 'content': f'Error: No JSON code block found in response. (Make sure the '
														f'response contains a valid JSON markdown block as expected)'})
			elif len(json_blocks) > 1:
				chat.append({'role': 'user', 'content': f'Error: Multiple JSON code blocks found in response. '
															 f'(There should only be one)'})

			else:
				try:
					rep = json.loads(json_blocks[0])
				except json.JSONDecodeError as e:
					chat.append({'role': 'user', 'content': f'Error decoding JSON: {e}'})
				else:
					ctx['rep'] = rep
					return rep

	def _implement_expand(self, ctx: JSONOBJ, chat: List[Dict[str, JSONDATA]]) -> None:
		chat.append({'role': 'user', 'content': self.expand_template.fill(**ctx, examples=self.examples)})
		code = self._collect_code(chat, dict(seed=ctx.get('seed', None)))
		ctx['expand_code'] = code

	def _implement_extract(self, ctx: JSONOBJ, chat: List[Dict[str, JSONDATA]]) -> None:
		chat.append({'role': 'user', 'content': self.extract_template.fill(**ctx, examples=self.examples)})
		code = self._collect_code(chat, dict(seed=ctx.get('seed', None)))
		ctx['extract_code'] = code
		ctx['extract_approach'] = self._confirm_choice(chat, ['state-based', 'trajectory-based'])

	def _implement_evaluate(self, ctx: JSONOBJ, chat: List[Dict[str, JSONDATA]]) -> None:
		chat.append({'role': 'user', 'content': self.evaluate_template.fill(**ctx, examples=self.examples)})
		code = self._collect_code(chat, dict(seed=ctx.get('seed', None)), allow_none=True)
		ctx['evaluate_code'] = code
		ctx['evaluate_approach'] = None if code is None \
			else self._confirm_choice(chat, ['score-based', 'comparison-based'])

	def _test_implementations(self, ctx: JSONOBJ, chat: List[Dict[str, JSONDATA]]) -> None:




		states = self._formalize_state(self.examples[0], ctx['rep'], ctx, chat, n=6, temperature=1.)

		ctx['example'] = self.examples[0]
		ctx['states'] = states

		# TODO: maybe generate unit tests, run the generated code, or ask for revisions based on formalization


	def _generate_variations(self, N: int, example: JSONOBJ, ctx: JSONOBJ, chat: List[Dict[str, JSONDATA]] = None, *,
							 n_parallel: int = None, max_tokens: int = 1024, clean_up: bool = True,
							 **kwargs) -> List[str]:
		if chat is None:
			chat = self.client.begin_chat()
		chat.append({'role': 'user', 'content': self.generate_template.fill(example=example, N=N, **ctx)})
		resp = self.client.step(chat, max_tokens=max_tokens, n=n_parallel or 1, **kwargs)

		if n_parallel is None:
			blocks = list(extract_code_blocks(chat[-1]['content'], ))

		else:
			blocks = [block for choice in resp['choices']
					  for block in extract_code_blocks(choice.get('text', choice.get('message', {}).get('content')),)]

		blocks = [block.replace('"""', '```').replace("'''", '```') for block in blocks]

		if clean_up:
			chat.pop()
			chat.pop()

		return blocks

	def _formalize_state(self, example: JSONOBJ, schema: JSONOBJ, ctx: JSONOBJ, chat: List[Dict[str, JSONDATA]], *,
						n: int = None, max_tokens: int = 1024, clean_up: bool = True,
						 **kwargs) -> Union[JSONOBJ, List[JSONOBJ]]:
		chat.append({'role': 'user', 'content': self.encode_template.fill(example=example, schema=schema, **ctx)})
		resp = self.client.step(chat, grammar=schema, max_tokens=max_tokens, n=n or 1, **kwargs)
		if clean_up:
			chat.pop()
			chat.pop()

		if n is None:
			state = json.loads(resp['choices'][0]['message']['content'])
			return state
		else:
			states = [json.loads(choice.get('text', choice.get('message', {}).get('content')))
								 for choice in resp['choices']]
			return states

	def _confirm_choice(self, chat: List[Dict[str, JSONDATA]], choices: List[str], *,
						clean_up: bool = True, max_tokens: int = 10) -> str:
		chat.append({'role': 'user', 'content': self.confirm_choice_template.fill(choices=choices)})
		resp = self.client.step(chat, max_tokens=max_tokens, grammar=choices)
		pick = chat[-1]['content']
		if clean_up:
			chat.pop()
			chat.pop()
		return pick

	def _collect_code(self, chat: List[Dict[str, JSONDATA]], params: Optional[JSONOBJ] = None, *,
					  allow_none: bool = False, allow_multiple: bool = False) -> str:
		if allow_multiple:
			raise NotImplementedError
		for resp in self.client.multi_turn(chat, params, max_retries=self._max_retries):
			py_blocks = list(extract_code_blocks(chat[-1]['content'], 'python'))

			if len(py_blocks) == 0:
				if allow_none:
					return None
				chat.append({'role': 'user', 'content': f'Error: No Python code block found in response. '
									f'(Make sure the response contains a valid Python markdown block as expected)'})
			elif len(py_blocks) > 1:
				chat.append({'role': 'user', 'content': f'Error: Multiple Python code blocks found in response. '
															 f'(There should only be one)'})

			else:
				code = py_blocks[0].strip()

				error = self._safety_concerns(code)
				if error:
					chat.append({'role': 'user', 'content':
						f'Error: Safety concerns detected in code: {error}. Can you try a different, safer '
						'implementation? (avoid unnecessary imports, side effects, and file operations)'
						if isinstance(error, str)
						else 'There seems to be a safety issue with the code you provided, can you try a different, '
						'safer implementation? (avoid unnecessary imports, side effects, and file operations)'})
				else:
					try:
						compile(code, '<string>', 'exec')
					except SyntaxError as e:
						chat.append({'role': 'user', 'content': f'Error: Syntax error in code: {e}'})
					else:
						return code

		raise BudgetExceededError(f'Failed to collect code after multiple attempts. '
								  f'Last response: {chat[-1]["content"]!r}')

	def _safety_concerns(self, code: str) -> Union[bool, str, None]:
		if self.safety_template is not None:
			safety_prompt = self.safety_template.fill(code=code)
			resp = self.client.step(safety_prompt, max_tokens=1024, grammar='yes/no')
			check = self.client.extract_response(resp)
			if check.strip().lower() == 'yes':
				return True

		# TODO: make somewhat stronger (e.g. using regex)
		sus_content = ['import os', 'import sys', 'import subprocess', 'import shutil', 'import pickle',
					   'open(', 'eval(', 'exec(',]
		for content in sus_content:
			if content in code:
				return True

		return None
