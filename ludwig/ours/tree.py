from .imports import *
from .. import AbstractTask
from ..util import StubTask, PromptTemplate, hash_str, extract_code_blocks
from ..abstract import AbstractJudge


@fig.component('ours/tree-builder')
class TreeBuilder(ClientStrategy):
	def __init__(self, task: 'AbstractTask',
				 rep_template: Union[PromptTemplate, str] = 'tree/rep',

				 expand_template: Union[PromptTemplate, str] = 'tree/expand',
				 extract_template: Union[PromptTemplate, str] = 'tree/extract',
				 evaluate_template: Union[PromptTemplate, str] = 'tree/evaluate',

				 encode_template: Union[PromptTemplate, str] = 'tree/encode',

				 confirm_choice_template: Union[PromptTemplate, str] = 'tree/confirm-choice',
				 safety_template: Union[PromptTemplate, str] = 'safe-code',
				 num_examples: int = 1, **kwargs):
		if not isinstance(rep_template, PromptTemplate):
			rep_template = PromptTemplate(rep_template)
		if not isinstance(expand_template, PromptTemplate):
			expand_template = PromptTemplate(expand_template)
		if not isinstance(extract_template, PromptTemplate):
			extract_template = PromptTemplate(extract_template)
		if not isinstance(evaluate_template, PromptTemplate):
			evaluate_template = PromptTemplate(evaluate_template)
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

		self._test_implementations(ctx, chat)

		ctx['chat'] = chat
		return ctx

	def _create_representation(self, ctx: JSONOBJ, chat: List[Dict[str, JSONDATA]]) -> JSONOBJ:
		prompt = self.rep_template.fill(**ctx, examples=self.examples)
		seed = ctx.get('seed', None)

		chat.append({'role': 'user', 'content': prompt})
		for resp in self.client.multi_turn(chat, dict(seed=seed), max_retries=3):
			json_blocks = list(extract_code_blocks(chat[-1]['content'], 'json'))

			if len(json_blocks) == 0:
				chat.append({'role': 'user', 'content': f'Error: No JSON code block found in response. (Make sure the '
														f'response contains a valid JSON markdown block as expected)'})
			elif len(json_blocks) > 1:
				chat.append({'role': 'user', 'content': f'Error: Multiple JSON code blocks found in response. '
															 f'(There should only be one)'})

			else:
				try:
					ctx['rep'] = json.loads(json_blocks[0])
				except json.JSONDecodeError as e:
					chat.append({'role': 'user', 'content': f'Error decoding JSON: {e}'})
				else:
					break

	def _implement_expand(self, ctx: JSONOBJ, chat: List[Dict[str, JSONDATA]]) -> None:

		

		raise NotImplementedError






