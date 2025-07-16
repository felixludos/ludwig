from .imports import *
from .files import Checkpointable
import ast, uuid
# from openai.types.chat.chat_completion_message_tool_call import ChatCompletionMessageToolCall as ToolCall
# from openai.types.chat.chat_completion_message_tool_call import Function


class ToolBase(fig.Configurable, Checkpointable, AbstractTool):
	def json(self) -> JSONOBJ:
		return self.schema()


# def parse_pythonic_tool_calls(raw_string: str) -> List[ToolCall]:
# 	"""
# 	Parses a stringified list of tool calls into a list of OpenAI-compatible
# 	ChatCompletionMessageToolCall Pydantic objects.
#
# 	Args:
# 		raw_string: A string representing a Python list of function calls,
# 					e.g., "[my_func(arg1='val1'), another_func(arg2=123)]"
#
# 	Returns:
# 		A list of ToolCall Pydantic objects.
# 	"""
# 	try:
# 		parsed_ast = ast.parse(raw_string, mode='eval')
# 		if not isinstance(parsed_ast.body, ast.List):
# 			raise ValueError("Input string must be a list of function calls.")
# 	except (ValueError, SyntaxError) as e:
# 		print(f"Error parsing the raw string: {e}")
# 		return []
#
# 	tool_calls = []
# 	for node in parsed_ast.body.elts:
# 		call_node = None
# 		if isinstance(node, ast.Call):
# 			# Handles format 1: [func1(a=1), func2(b=2)]
# 			call_node = node
# 		elif isinstance(node, ast.Constant) and isinstance(node.value, str):
# 			# Handles format 2: ['func1(a=1)', 'func2(b=2)']
# 			try:
# 				# We need to parse the string content of the node
# 				inner_expr = ast.parse(node.value, mode='eval')
# 				if isinstance(inner_expr.body, ast.Call):
# 					call_node = inner_expr.body
# 			except (ValueError, SyntaxError):
# 				# The string was not a valid function call, so we skip it
# 				continue
#
#
# 		if call_node is None:
# 			raise ValueError(f"Invalid function call format: {node}")
#
# 		# 1. Extract function name and arguments
# 		function_name = call_node.func.id
# 		arguments_dict = {
# 			keyword.arg: ast.literal_eval(keyword.value)
# 			for keyword in call_node.keywords
# 		}
#
# 		# 2. Create the Pydantic `Function` object
# 		# The arguments must be a JSON string.
# 		function_obj = Function(
# 			name=function_name,
# 			arguments=json.dumps(arguments_dict)
# 		)
#
# 		# 3. Create the `ToolCall` Pydantic object
# 		tool_call_obj = ToolCall(
# 			id=f"call_{uuid.uuid4().hex}",
# 			function=function_obj,
# 			type='function',
# 		)
# 		tool_calls.append(tool_call_obj)
#
# 	return tool_calls

# from pydantic import BaseModel
#
# class SimpleFunction(BaseModel):
# 	name: str
# 	arguments: Any # JSON string
#
# class SimpleToolCall(BaseModel):
# 	function: SimpleFunction
# 	type: str = 'function'
# 	id: str

def parse_json_tool_calls(raw_string: str) -> List[JSONOBJ]:
	"""
	Parses a string of semicolon-separated JSON tool calls into a list of
	OpenAI-compatible ChatCompletionMessageToolCall Pydantic objects.

	Each JSON object should have a "name" and "parameters" key.

	Args:
		raw_string: A string of semicolon-separated JSON objects.
					e.g., '{"name": "func1", "parameters": {"a": 1}}; {"name": "func2", "parameters": {"b": 2}}'

	Returns:
		A list of ToolCall Pydantic objects.
	"""
	# Split the raw string by the semicolon to get individual JSON strings.
	json_strings = [s.strip() for s in raw_string.split(';') if s.strip()]
	if not json_strings:
		return []

	tool_calls = []
	for json_str in json_strings:
		try:
			fulldata = json.loads(json_str)

		except json.JSONDecodeError:
			print(f"Warning: Could not decode JSON for part: {json_str}")
			continue
		else:
			calls = [fulldata] if isinstance(fulldata, dict) else fulldata
			for data in calls:
				function_name = data.get("name")
				# The input format uses "parameters", which we map to "arguments"
				arguments_dict = data.get("parameters", {})

				if not function_name:
					print(f"Warning: JSON object is missing 'name': {json_str}")
					continue

				function_obj = dict(name=function_name, arguments=json.dumps(arguments_dict))
				tool_call_obj = dict(id=f"call_{uuid.uuid4().hex}", function=function_obj, type='function')
				tool_calls.append(tool_call_obj)

	return tool_calls


# class SimpleTool(ToolBase):


def _parse_arguments(arg_string: str) -> Dict[str, Any]:
	"""
	Parses a string of Python-like keyword arguments into a dictionary using regex.

	This helper function is designed to be robust. It can handle:
	- Strings in single or double quotes.
	- Commas within quoted strings.
	- Unquoted strings (which are treated as string literals).
	- Other Python literals like numbers, booleans, and None.
	"""
	if not arg_string.strip():
		return {}

	# This regex pattern finds all key-value argument pairs.
	# Pattern Explanation:
	# (\w+)\s*=\s* - Captures the argument name (key).
	# (             - Starts a capturing group for the value.
	#   '[^']*'    - Matches a single-quoted string.
	#   |           - OR
	#   "[^"]*"    - Matches a double-quoted string.
	#   |           - OR
	#   [^,]+       - Matches an unquoted value (anything not a comma).
	# )             - Ends the value-capturing group.
	# The order of alternatives is important: quoted strings are matched first.
	arg_pattern = re.compile(r"(\w+)\s*=\s*('[^']*'|\"[^\"]*\"|[^,]+)")

	args_dict = {}
	for key, value_str in arg_pattern.findall(arg_string):
		value_str = value_str.strip()
		try:
			# ast.literal_eval safely evaluates string literals of Python types.
			value = ast.literal_eval(value_str)
		except (ValueError, SyntaxError):
			# If literal_eval fails, it's likely an unquoted string
			# (e.g., `name=Alice` instead of `name='Alice'`).
			# In this case, we simply treat it as a string.
			value = value_str

		args_dict[key] = value

	return args_dict


# --- Main Parsing Function ---

def parse_pythonic_tool_calls(raw_string: str) -> List[JSONOBJ]:
	"""
	Parses a string of tool calls into a list of ToolCall objects using regex.

	This version is more tolerant of minor syntactic errors (like missing commas
	between calls or unquoted string values) than a strict `ast.parse` approach.
	It can also handle inputs that are string-encoded lists of calls, even
	when nested inside other strings (e.g., ""['call1']"").

	Args:
	   raw_string: A string representing Python function calls.
				e.g., "[my_func(arg1='val1') another_func(arg2=123)]"
				or "['my_func(arg1=\\'val1\\')', 'another_func(arg2=123)']"
				or "\"['get_current_weather(city=Barcelona)']\""

	Returns:
	   A list of ToolCall Pydantic objects.
	"""
	# --- Pre-processing to unwrap nested string representations ---
	content = raw_string
	# Repeatedly use literal_eval to "peel" layers of string quoting.
	# For example, from ""['call1']"" -> "['call1']" -> ['call1']
	while isinstance(content, str):
		try:
			content = ast.literal_eval(content)
		except (ValueError, SyntaxError):
			# If it's no longer a valid literal, we've unwrapped as far as we can.
			break

	# --- Prepare list of strings to search for function calls ---
	if isinstance(content, list):
		# If we successfully evaluated to a list, use its contents.
		strings_to_search = content
	elif isinstance(content, str):
		# If we ended up with a string, search within that string.
		strings_to_search = [content]
	else:
		# If the input is some other unsupported type, we can't process it.
		return []

	# This regex finds all occurrences of the pattern: function_name(...)
	# It captures the function name and the raw string of arguments inside
	# the parentheses.
	call_pattern = re.compile(r"(\w+)\s*\(([^)]*)\)")

	tool_calls = []
	for text_block in strings_to_search:
		if not isinstance(text_block, str):
			# This handles cases where a list might contain non-string items.
			continue

		for match in call_pattern.finditer(text_block):
			function_name, arg_string = match.groups()

			try:
				# Use the helper to parse the extracted argument string
				arguments_dict = _parse_arguments(arg_string)

				# Create the Pydantic Function object, serializing args to JSON
				# function_obj = Function(
				# 	name=function_name,
				# 	arguments=json.dumps(arguments_dict)
				# )
				# # Create the final ToolCall object
				# tool_call_obj = ToolCall(function=function_obj, type='function', id=f"call_{uuid.uuid4().hex}")
				#
				function_obj = dict(
					name = function_name,
					# arguments = json.dumps(arguments_dict)
					arguments = arguments_dict
				)
				tool_call_obj = dict(function=function_obj, type='function', id=f"call_{uuid.uuid4().hex}")

				tool_calls.append(tool_call_obj)

			except Exception as e:
				# If parsing a specific call fails, print an error and skip it
				# to avoid failing the entire process.
				print(f"Could not parse call for function '{function_name}': {e}")
				continue

	return tool_calls



