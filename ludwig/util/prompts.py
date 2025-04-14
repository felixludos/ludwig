from .imports import *
from .files import repo_root, hash_str


@fig.component('prompt-template')
class PromptTemplate:
	def __init__(self, template: Union[str, Path], **kwargs):
		super().__init__(**kwargs)
		self.template = template
		self._loaded_template = False
		self._template_data = self._process_template(template)
		self._template_code = hash_str(self._template_data)

	def _process_template(self, template):
		if isinstance(template, Path) or '{' not in template:
			template = self._load_template(Path(template))
		return template


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

	@property
	def loaded_template(self) -> bool:
		return self._loaded_template

	@property
	def ident(self) -> str:
		if self._loaded_template:
			return str(self.template)
		return self.code

	@property
	def code(self) -> str:
		return self._template_code[:4]

	def json(self) -> JSONOBJ:
		return {
			'template': str(self.template),
			'code': self._template_code,
		}

	def fill(self, **kwargs) -> str:
		"""
		Fill the template with the given keyword arguments.
		"""
		return self._template_data.format(**kwargs)

