from .imports import *
import ast


class AbstractParser:
	def prepare(self):
		raise NotImplementedError

	def parse(self, text: str) -> JSONABLE:
		raise NotImplementedError

	def realize(self, data: JSONABLE) -> Any:
		raise NotImplementedError


class UnsafeCodeError(Exception):
	"""
	Exception raised for unsafe code execution.
	"""
	def __init__(self, message: str):
		super().__init__(message)
		self.message = message

	def __str__(self):
		return f"UnsafeCodeError: {self.message}"



@fig.component('python-parser')
class PythonParser(AbstractParser):
	"""
	Parse Python code.
	"""
	def __init__(self, *, safe: bool = True, raise_errors: bool = False, **kwargs):
		super().__init__(**kwargs)
		self.safe = safe
		self.raise_errors = raise_errors

	def prepare(self):
		pass

	_DISALLOWED_NAMES = {
		"exec", "eval", "compile", "open", "input", "os", "sys", "subprocess",
		"__import__", "globals", "locals", "compile", "breakpoint", "exit", "quit"
	}

	def is_code_safe(self, code: str) -> Optional[str]:
		try:
			tree = ast.parse(code)
			for node in ast.walk(tree):
				if isinstance(node, ast.Call):
					if isinstance(node.func, ast.Name) and node.func.id in self._DISALLOWED_NAMES:
						return f"Disallowed function call: {node.func.id}"
					if isinstance(node.func, ast.Attribute) and node.func.attr in self._DISALLOWED_NAMES:
						return f"Disallowed attribute: {node.func.attr}"
				elif isinstance(node, ast.Import):
					for alias in node.names:
						if alias.name.split('.')[0] in self._DISALLOWED_NAMES:
							return f"Disallowed import: {alias.name}"
				elif isinstance(node, ast.ImportFrom):
					if node.module and node.module.split('.')[0] in self._DISALLOWED_NAMES:
						return f"Disallowed import from: {node.module}"
				elif isinstance(node, ast.Name):
					if node.id in self._DISALLOWED_NAMES:
						return f"Disallowed usage of: {node.id}"
		except SyntaxError as e:
			# raise self._UnsafeCodeError(f"Syntax error: {e}")
			return f"Syntax error: {e}"

	@staticmethod
	def is_syntax_valid(code: str) -> Optional[str]:
		try:
			ast.parse(code)
		except SyntaxError as e:
			return str(e)

	def realize(self, items: List[Union[JSONOBJ, str]]) -> List[Dict[str, Any]]:
		"""
		Realize the parsed data into executable code.
		"""
		results = []
		for raw in items:
			item = {}
			if isinstance(raw, str):
				item['code'] = raw
			else:
				item.update(raw)
			code = item["code"]
			if self.safe and 'error' in item:
				print(f"⚠️ Unsafe code block skipped:\n{code}")
				continue

			error = None
			namespace: Dict[str, Any] = {}
			try:
				exec(code, namespace)
			except Exception as e:
				item['run_error'] = f"Error while executing code block:\n{code}\n\nError: {e}"
			else:
				namespace = None
			if namespace is not None:
				item['namespace'] = namespace
			results.append(item)
		return results

	def parse(self, text: str) -> List[JSONOBJ]:
		code_blocks = re.findall(r"```python(.*?)```", text, re.DOTALL)

		items = []
		for block in code_blocks:
			item = {}

			code = block.strip()
			item['code'] = code

			unsafe = self.is_code_safe(code)
			if unsafe:
				item['error'] = unsafe

			items.append(item)

		return items



