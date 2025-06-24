from .imports import *
from .files import Checkpointable
import ast, uuid
from openai.types.chat.chat_completion_message_tool_call import ChatCompletionMessageToolCall as ToolCall
from openai.types.chat.chat_completion_message_tool_call import Function


class ToolBase(fig.Configurable, Checkpointable, AbstractTool):
	def json(self) -> JSONOBJ:
		return self.schema()


def parse_pythonic_tool_calls(raw_string: str) -> List[ToolCall]:
	"""
	Parses a stringified list of tool calls into a list of OpenAI-compatible
	ChatCompletionMessageToolCall Pydantic objects.

	Args:
		raw_string: A string representing a Python list of function calls,
					e.g., "[my_func(arg1='val1'), another_func(arg2=123)]"

	Returns:
		A list of ToolCall Pydantic objects.
	"""
	try:
		parsed_ast = ast.parse(raw_string, mode='eval')
		if not isinstance(parsed_ast.body, ast.List):
			raise ValueError("Input string must be a list of function calls.")
	except (ValueError, SyntaxError) as e:
		print(f"Error parsing the raw string: {e}")
		return []

	tool_calls = []
	for node in parsed_ast.body.elts:
		call_node = None
		if isinstance(node, ast.Call):
			# Handles format 1: [func1(a=1), func2(b=2)]
			call_node = node
		elif isinstance(node, ast.Constant) and isinstance(node.value, str):
			# Handles format 2: ['func1(a=1)', 'func2(b=2)']
			try:
				# We need to parse the string content of the node
				inner_expr = ast.parse(node.value, mode='eval')
				if isinstance(inner_expr.body, ast.Call):
					call_node = inner_expr.body
			except (ValueError, SyntaxError):
				# The string was not a valid function call, so we skip it
				continue


		if call_node is None:
			raise ValueError(f"Invalid function call format: {node}")

		# 1. Extract function name and arguments
		function_name = call_node.func.id
		arguments_dict = {
			keyword.arg: ast.literal_eval(keyword.value)
			for keyword in call_node.keywords
		}

		# 2. Create the Pydantic `Function` object
		# The arguments must be a JSON string.
		function_obj = Function(
			name=function_name,
			arguments=json.dumps(arguments_dict)
		)

		# 3. Create the `ToolCall` Pydantic object
		tool_call_obj = ToolCall(
			id=f"call_{uuid.uuid4().hex}",
			function=function_obj,
			type='function',
		)
		tool_calls.append(tool_call_obj)

	return tool_calls


def parse_json_tool_calls(raw_string: str) -> List[ToolCall]:
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
			data = json.loads(json_str)
			function_name = data.get("name")
			# The input format uses "parameters", which we map to "arguments"
			arguments_dict = data.get("parameters", {})

			if not function_name:
				print(f"Warning: JSON object is missing 'name': {json_str}")
				continue

			function_obj = Function(name=function_name, arguments=json.dumps(arguments_dict))
			tool_call_obj = ToolCall(id=f"call_{uuid.uuid4().hex}", function=function_obj, type='function')
			tool_calls.append(tool_call_obj)

		except json.JSONDecodeError:
			print(f"Warning: Could not decode JSON for part: {json_str}")
			continue

	return tool_calls


# class SimpleTool(ToolBase):





