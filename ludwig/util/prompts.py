from .imports import *
from .files import repo_root, hash_str
from omnibelt import pformat_vars
from .abstract import AbstractTool
from .tools import ToolBase


class AbstractTemplate:
	def fill(self, **kwargs) -> str:
		"""
		Fill the template with the given keyword arguments.
		"""
		raise NotImplementedError

	def json(self) -> JSONOBJ:
		raise NotImplementedError

	@property
	def ident(self) -> str:
		raise NotImplementedError

	@property
	def code(self) -> str:
		raise NotImplementedError


class AbstractFormalizer:
	@property
	def ident(self) -> Optional[str]:
		return None

	def prepare(self, task: 'AbstractTask'):
		pass
	
	def schema(self) -> JSONOBJ:
		raise NotImplementedError
	
	def compare(self, context: JSONOBJ, formal: JSONOBJ) -> JSONOBJ:
		return {}

	def correct(self, context: JSONOBJ, formal: JSONOBJ) -> bool:
		raise NotImplementedError

	def formalize(self, context: JSONOBJ) -> JSONOBJ:
		raise NotImplementedError

	def formalization_args(self, context: JSONOBJ) -> JSONOBJ:
		raise NotImplementedError

	def json(self):
		return {}


class SimpleFormalizer(AbstractFormalizer):
	def correct(self, context: JSONOBJ, formal: JSONOBJ) -> bool:
		if formal is None:
			return None
		gt = self.formalize(context)
		assert len(gt)
		for key, val in gt.items():
			if val != formal.get(key, object()):
				return False
		return True

	def formalize(self, context: JSONOBJ) -> JSONOBJ:
		info = self.formalization_args(context)
		return self.default_formalize(**info)

	def default_formalize(self):
		raise NotImplementedError


_schema_bad_keys = {'uniqueItems', '$schema'}
def filter_schema(data):
	if isinstance(data, dict):
		if data.get('type') == 'array' and 'items' not in data:
			raise ValueError("Array schema must have 'items' key")
		if 'items' in data and isinstance(data['items'], list):
			assert len(data['items']) == 1
			data['items'] = data['items'][0]
		return {key: filter_schema(val) for key, val in data.items() if key not in _schema_bad_keys}
	if isinstance(data, list):
		return [filter_schema(item) for item in data]
	return data


@fig.component('custom-formalizer')
class Custom_Formalizer(fig.Configurable, SimpleFormalizer):
	def __init__(self, path: str, index: int = None, **kwargs):
		if isinstance(path, str):
			path = Path(pformat(path, root=repo_root()))
		super().__init__(**kwargs)
		self.path = path
		self.index = index

		self.extractor = None

		if not path.exists():
			raise FileNotFoundError(path)

		data = None
		if path.suffix == '.jsonl':
			with path.open('r') as f:
				for i, line in enumerate(f):
					if index is None or index == i:
						data = json.loads(line)
		elif path.suffix == '.json':
			reps = json.load(path.open('r'))
			if not isinstance(reps, list):
				reps = [reps]
			if index is None:
				if len(reps) > 1:
					raise ValueError(f'Multiple representations found in {path}, please specify an index')
				index = 0
			if not (-len(reps) <= index < len(reps)):
				raise ValueError(f'Invalid index: {index} < {len(reps)}')
			data = reps[index]
		else:
			raise ValueError(f'Unsupported file type: {path}')
		if data is None:
			raise ValueError(f'Invalid index: {index!r}.')
		self.data = data
		self._schema = None
		self._code = None
		self._fn = None

	def json(self):
		return {
			'path': str(self.path),
			'index': self.index,
			**super().json(),
		}

	def prepare(self, task: 'AbstractTask'):
		super().prepare(task)
		self.extractor = task.formalizer()

		if 'rep' not in self.data:
			raise ValueError(f'Missing rep')
		self._schema = filter_schema(self.data['rep'])
		if 'encode' not in self.data:
			raise ValueError(f'Missing encode')
		self._code = self.data['encode']

		objs = {}
		exec(self._code, objs)
		self._fn = objs.get('encode')
		if self._fn is None:
			raise ValueError(f'Missing `encode` fn')

	def schema(self) -> JSONOBJ:
		return self._schema

	def formalize(self, context: JSONOBJ) -> JSONOBJ:
		info = self.extractor.formalization_args(context)
		return self._fn(**info)



@fig.modifier('tool-adapter')
class ToolAdapter(ToolBase):
	def __init__(self, adapter_path: Union[Path, str], rep_index: int, adapter_description: str = None, **kwargs):
		if isinstance(adapter_path, str):
			adapter_path = Path(adapter_path.format(root=repo_root()))
		super().__init__(**kwargs)
		self.rep_index = rep_index
		self.adapter_path = adapter_path
		self._adapter_description = adapter_description
		self.decoder_fn = None
		self.adapter_rep = None

	def json(self) -> 'JSONLIKEOBJ':
		return {
			'adapter_path': str(self.adapter_path),
			'rep_index': self.rep_index,
			# 'adapter_description': self._adapter_description,
			**super().json()
		}

	def prepare(self, task: 'AbstractTask') -> 'Self':
		super().prepare(task)
		if self.adapter_path.is_dir():
			self.adapter_path = self.adapter_path / 'log-formal.json'
		if not self.adapter_path.exists():
			raise FileNotFoundError(f'Adapter file not found: {self.adapter_path}')

		reps = json.load(self.adapter_path.open('r'))
		if not (-len(reps) <= self.rep_index < len(reps)):
			raise ValueError(f'Invalid rep index: {self.rep_index} < {len(reps)}')
		rep = reps[self.rep_index]

		assert 'decode' in rep, f'Adapter is missing the decode function'
		code = rep['decode']
		objs = {}
		exec(code, objs)
		assert 'decode' in objs, f'Adapter is missing the decode function'
		self.decoder_fn = objs.get('decode')

		assert 'rep' in rep, f'Adapter is missing the representation schema'
		self.adapter_rep = rep['rep']
		if 'name' in self.adapter_rep:
			del self.adapter_rep['name']
		if 'description' in self.adapter_rep:
			del self.adapter_rep['description']

		return self

	def description(self) -> str:
		if self._adapter_description is not None:
			return self._adapter_description
		return super().description()

	def schema(self, style: str = None) -> JSONOBJ:
		if self.adapter_rep is None:
			raise ValueError(f'ToolAdapter has not been prepared with a task.')
		return {
			'type': 'function', 'function': {
				"name": self.name,
				"description": self.description(),
				"parameters": self.adapter_rep,
			}
		}

	def decode(self, raw: JSONOBJ) -> JSONOBJ:
		if self.decoder_fn is None:
			raise ValueError(f'ToolAdapter has not been prepared with a task.')
		return self.decoder_fn(raw)

	def call(self, arguments: JSONDATA, *, seed: Optional[int] = None) -> str:
		assert isinstance(arguments, dict), f'Invalid arguments type: {arguments}'

		try:
			fixed = self.decode(arguments)
		except:
			raise ToolError(f'The input state was not provided in the correct format.')

		out = super().call(fixed)
		return out



@fig.component('prompt-template')
class PromptTemplate(fig.Configurable, AbstractTemplate):
	def __init__(self, template: Union[str, Path], ident: str = None, autostrip: bool = True, **kwargs):
		super().__init__(**kwargs)
		self.template = template
		self._template_name = ident
		self._loaded_template = False
		self._template_data = self._process_template(template)
		self._template_code = hash_str(self._template_data)
		self._autostrip = autostrip

	def _process_template(self, template):
		if isinstance(template, Path) or '{' not in template:
			template = self._load_template(Path(template))
		return template

	def _load_template(self, raw: Path) -> str:
		self._loaded_template = True
		path = raw
		if path.suffix == '':
			candidates = list(repo_root().joinpath('assets', 'prompts').glob(f'{path}.*'))
			if len(candidates) == 0:
				raise FileNotFoundError(f'prompt template not found: {raw}')
			if len(candidates) > 1:
				raise ValueError(f'Expected exactly one prompt template for {path.name}, found {len(candidates)}')
			path = candidates[0]
		if not path.exists():
			path = repo_root().joinpath('assets', 'prompts') / path
		if not path.exists():
			raise FileNotFoundError(f'prompt template not found: {raw}')
		return path.read_text(encoding='utf-8').strip()

	def __str__(self):
		return f'PromptTemplate({self.ident})'

	@property
	def loaded_template(self) -> bool:
		return self._loaded_template

	@property
	def ident(self) -> str:
		if self._template_name is not None:
			return self._template_name
		if self._loaded_template:
			return str(self.template).replace('/', '-')
		return self.code[:4]

	@property
	def code(self) -> str:
		return self._template_code

	def json(self) -> JSONOBJ:
		return {
			'template': str(self.template),
			'code': self._template_code,
		}

	def get_raw(self) -> str:
		return self._template_data

	def variables(self) -> Iterator[str]:
		yield from pformat_vars(self._template_data)

	def fill(self, **kwargs) -> str:
		"""
		Fill the template with the given keyword arguments.
		"""
		# return self._template_data.format(**kwargs)
		res = pformat(self._template_data, kwargs, json=json)
		if self._autostrip:
			res = res.strip()
		return res



@fig.component('chat-template')
class ChatTemplate(fig.Configurable, AbstractTemplate):
	def __init__(self, chat: List[Dict[str, Union[str, Path]]], **kwargs):
		super().__init__(**kwargs)
		self.chat = chat
		self._loaded_template = False
		self._template_data = self._process_chat_template(chat)
		self._template_code = hash_str(str(self._template_data))

	@property
	def loaded_template(self) -> bool:
		return self._loaded_template

	@property
	def ident(self) -> str:
		if self._loaded_template:
			return str(self.chat)
		return self.code

	def _load_template(self, raw: Path) -> str:
		self._loaded_template = True
		path = raw
		if path.suffix == '':
			path = path.with_suffix('.txt')
		if not path.exists():
			path = repo_root().joinpath('assets', 'prompts') / path
		if not path.exists():
			raise FileNotFoundError(f'prompt template not found: {raw}')
		return path.read_text(encoding='utf-8').strip()

	def _process_chat_template(self, chat: List[Dict[str, str]]) -> List[Dict[str, str]]:
		msgs = []
		for msg in chat:
			assert 'role' in msg and 'content' in msg, 'Chat message must contain role and content'
			template = msg['content']
			if isinstance(template, Path) or '{' not in template:
				template = self._load_template(Path(template))
			msgs.append({'role': msg['role'], 'content': template})
		return msgs

	@property
	def code(self) -> str:
		return self._template_code[:4]

	def json(self) -> JSONOBJ:
		return {
			'template': str(self.chat),
			'code': self._template_code,
		}


