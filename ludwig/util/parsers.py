from .imports import *
import ast
import builtins
from RestrictedPython import compile_restricted_exec, compile_restricted_eval
from RestrictedPython import safe_globals
from RestrictedPython.PrintCollector import PrintCollector
from RestrictedPython.Guards import guarded_iter_unpack_sequence as _iter_unpack_sequence_
from RestrictedPython.Guards import (
    guarded_iter_unpack_sequence,
    full_write_guard,
)
from RestrictedPython.Eval import (
	default_guarded_getiter as _getiter,
	default_guarded_getattr as _getattr,
	default_guarded_getitem as _getitem,
)

import ast
import io
import contextlib


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
		self.safe_globals = None
		self.raise_errors = raise_errors

	def json(self) -> JSONOBJ:
		return {
			'safe': self.safe,
			'raise_errors': self.raise_errors,
		}

	def prepare(self):

		my_globals = dict(safe_globals)

		# Add standard types
		for name in ('list', 'dict', 'set', 'tuple', 'object', 'type', 'isinstance', 'callable'):
			my_globals[name] = getattr(builtins, name)

		# Add basic exceptions
		for name in ('Exception', 'ValueError', 'KeyError', 'IndexError', 'TypeError', 'AttributeError', 'NameError'):
			my_globals[name] = getattr(builtins, name)

		# Add commonly used functions
		for name in ('zip', 'map', 'filter', 'any', 'all', 'sorted', 'reversed', 'next', 'enumerate', 'len', 'range'):
			my_globals[name] = getattr(builtins, name)

		my_globals.update({
			'_iter_unpack_sequence_': guarded_iter_unpack_sequence,
			'_write_': full_write_guard,
			'_getattr_': _getattr,
			'_getiter_': _getiter,
			'_getitem_': _getitem,
			'_print_': PrintCollector,
		})

		self.safe_globals = my_globals

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

	def realize(self, raw: Union[JSONOBJ, str], namespace: Dict[str, Any] = None) -> Dict[str, Any]:
		"""
		Realize the parsed data into executable code.
		"""
		safe_env = self.safe_globals.copy()

		local_vars: Dict[str, Any] = {}
		if namespace is not None:
			local_vars.update(namespace)

		item = {}
		if isinstance(raw, str):
			item['code'] = raw
		else:
			item.update(raw)
		code = item["code"]

		if 'unsafe' not in item:
			item['unsafe'] = self.is_code_safe(code)
		if self.safe and item.get('unsafe') is not None:
			# print(f"⚠️ Unsafe code block skipped:\n{item['unsafe']}")
			return item

		stdout = io.StringIO()
		stderr = io.StringIO()
		# safe_env['_print_'] = lambda *args: print(*args, file=stdout)

		try:
			parsed = ast.parse(code)
		except SyntaxError as e:
			traceback.print_exc(file=stderr)

			item['error'] = e
			if self.raise_errors:
				raise UnsafeCodeError(str(e))
		else:
			body = parsed.body[:-1] if parsed.body else []
			last = parsed.body[-1] if parsed.body else None

			# collect stdout and stderr in a buffer
			with redirect_stdout(stdout), redirect_stderr(stderr):
				try:
					if body:
						mod = ast.Module(body, type_ignores=[])
						compiled, _errors, _used_names, _warnings = compile_restricted_exec(mod, filename='<exec>')
						exec(compiled, safe_env, local_vars)
						safe_env.update(local_vars)

					if isinstance(last, ast.Expr):
						expr_src = ast.unparse(last.value)
						compiled_expr, _errors, _used_names, _warnings = compile_restricted_eval(
							expr_src, filename='<eval>'
						)
						item['result'] = eval(compiled_expr, safe_env, local_vars)
					elif last:
						compiled_last, _errors, _used_names, _warnings = compile_restricted_exec(
							ast.Module([last], type_ignores=[]), filename='<exec>'
						)
						exec(compiled_last, safe_env, local_vars)
				except Exception as e:
					# print full error with traceback
					traceback.print_exc(file=stderr)
					if self.raise_errors:
						raise UnsafeCodeError(str(e))
					item['error'] = e

		if stdout.getvalue():
			item['stdout'] = stdout.getvalue()
		if stderr.getvalue():
			item['stderr'] = stderr.getvalue()
		if local_vars:
			item['local_vars'] = local_vars
		return item

	def parse(self, text: str) -> List[JSONOBJ]:
		code_blocks = re.findall(r"```python(.*?)```", text, re.DOTALL)

		if not code_blocks:
			code_blocks = re.findall(r"```(.*?)```", text, re.DOTALL)

		items = []
		for block in code_blocks:
			item = {}

			code = block.strip()
			item['code'] = code

			item['unsafe'] = self.is_code_safe(code)

			items.append(item)

		return items



