from .imports import *
import uuid
import ast



class AbstractParser:
	def parse(self, text: str, context: JSONOBJ = None) -> JSONOBJ:
		"""
		Parse a text message into a structured format.
		This method should be overridden by subclasses.
		"""
		raise NotImplementedError("Subclasses must implement this method.")


def test_parse_message():
	# example short response from qwen
	response = ("<think>\nI will use the `get_current_weather` function to get the weather in Barcelona.\n"
				"</think>\n\nThe current weather in Barcelona is sunny with a temperature of 25 degrees Celsius.")

	parser = MessageParser()

	parsed = parser.parse(response)
	assert parsed['reasoning_content'] == "I will use the `get_current_weather` function to get the weather in Barcelona."
	assert parsed['content'] == "The current weather in Barcelona is sunny with a temperature of 25 degrees Celsius."


class MessageParser(AbstractParser):
	def parse(self, text: str, data: JSONOBJ = None, resp: JSONOBJ = None, *, role: str = 'assistant') -> JSONOBJ:
		context = data or {}
		content = text.strip()
		message = {'content': None, 'role': role, 'tool_calls': []}

		toolnames = [tool['function']['name'] for tool in context.get('tools', [])
					 if 'name' in tool.get('function', {})]

		# region extract reasoning content
		match = re.search(r"(.*?)<think>(.*?)</think>(.*)", content, re.DOTALL)
		if match:
			# Group 1 contains the content inside the tags (reasoning)
			reasoning = match.group(2).strip()

			# Group 2 contains the content after the closing tag
			content1 = match.group(1).strip()
			content2 = match.group(3).strip()

			# Combine the content before and after the reasoning
			content = f"{content1}\n{content2}".strip()

			message['reasoning_content'] = reasoning

		# endregion

		# region extract tool calls
		tool_call_pattern = r"<(tool_calls?)>(.*?)</\1>"
		# combined pattern


		# 1. Find all tool call blocks in the content
		tool_call_blocks = re.findall(tool_call_pattern, content, re.DOTALL)

		if tool_call_blocks:
			all_parsed_calls = []
			# 2. Iterate through each found block and parse its content
			for tag, block in tool_call_blocks:
				lines = block.strip().splitlines()
				for line in lines:
					if line.startswith('[') and line.endswith(']'):
						all_parsed_calls.extend(parse_pythonic_tool_calls(line))
						all_parsed_calls.extend(parse_json_tool_calls(line))
					elif line.startswith('{') and line.endswith('}'):
						all_parsed_calls.extend(parse_json_tool_calls(line))

			# 3. If any valid tool calls were parsed, update the message
			if all_parsed_calls:
				# Remove all tool call blocks from the original content string
				content = re.sub(tool_call_pattern, "", content, flags=re.DOTALL).strip()
				message['tool_calls'] = all_parsed_calls
			else:
				# No valid calls were parsed from the found blocks
				raise ValueError(f"No valid tool calls found in content: {tool_call_blocks}")

		else:
			lines = content.splitlines()
			clean_content = []
			tool_calls = []
			for line in lines:
				if (line.startswith('[') and line.endswith(']')) or any(line.startswith(name) for name in toolnames):
					calls = parse_pythonic_tool_calls(line)
					if calls:
						tool_calls.extend(calls)
					else:
						try:
							calls = parse_json_tool_calls(line)
						except:
							clean_content.append(line)
						else:
							if calls:
								tool_calls.extend(calls)
							else:
								clean_content.append(line)

				elif (line.startswith('{') and line.endswith('}')) or any(name in line for name in toolnames):
					calls = parse_json_tool_calls(line)
					if calls:
						tool_calls.extend(calls)
					else:
						clean_content.append(line)
				else:
					clean_content.append(line)
			if tool_calls:
				content = '\n'.join(clean_content).strip()
				message['tool_calls'] = tool_calls

		# endregion

		# filter out <answer> tags, setting the content to `content`
		if '<answer>' in content or '</answer>' in content:
			answer_pattern = r"<answer>(.*?)</answer>"
			answer_match = re.search(answer_pattern, content, re.DOTALL)
			if answer_match:
				# Extract the content inside the <answer> tags
				answer_content = answer_match.group(1).strip()
				# Remove the <answer> tags from the content
				content = answer_content
			else:
				raise ValueError("No valid <answer> tags found in content.")
		message['content'] = content.strip()
		return message


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
			# print(f"Warning: Could not decode JSON for part: {json_str}")
			continue
		else:
			calls = [fulldata] if isinstance(fulldata, dict) else fulldata
			for data in calls:
				function_name = data.get("name")
				# The input format uses "parameters", which we map to "arguments"
				arguments_dict = data.get("parameters", data.get("arguments", {}))

				if not function_name:
					print(f"Warning: JSON object is missing 'name': {json_str}")
					continue

				function_obj = dict(name=function_name, arguments=json.dumps(arguments_dict))
				tool_call_obj = dict(id=f"call_{uuid.uuid4().hex}", function=function_obj, type='function')
				tool_calls.append(tool_call_obj)

	return tool_calls


def _parse_arguments(arg_string: str) -> Dict[str, Any]:
    """
    Parses a string of Python keyword arguments into a dictionary using AST.
    This version handles both quoted literals (e.g., 'val') and unquoted
    name-like values (e.g., city=Barcelona), treating the latter as strings.
    """
    if not arg_string.strip():
        return {}
    try:
        # Wrap arguments in a dummy function call to parse them
        call_node = ast.parse(f"dummy({arg_string})", mode='eval').body
        args = {}
        for kw in call_node.keywords:
            arg_name = kw.arg
            arg_value_node = kw.value
            # If the value is an ast.Name, it's an unquoted value like 'Barcelona'.
            # We will treat its ID ('Barcelona') as a string.
            if isinstance(arg_value_node, ast.Name):
                args[arg_name] = arg_value_node.id
            # For all other literal types (strings, numbers, lists, dicts, etc.),
            # ast.literal_eval is the safe way to get the Python object.
            else:
                args[arg_name] = ast.literal_eval(arg_value_node)
        return args
    except (SyntaxError, ValueError) as e:
        print(f"Could not parse arguments using AST: '{arg_string}'. Error: {e}")
        return {}


def parse_pythonic_tool_calls(raw_string: str) -> List[JSONOBJ]:
	"""
	Parses a string of tool calls into a list of ToolCall objects using regex.

	Args:
	   raw_string: A string representing Python function calls.

	Returns:
	   A list of ToolCall-like dictionary objects.
	"""
	# --- Pre-processing to unwrap nested string representations ---
	content = raw_string
	while isinstance(content, str):
		try:
			content = ast.literal_eval(content)
		except (ValueError, SyntaxError):
			break

	# --- Prepare list of strings to search for function calls ---
	if isinstance(content, list):
		strings_to_search = content
	elif isinstance(content, str):
		strings_to_search = [content]
	else:
		return []

	# This regex correctly finds each function call.
	call_pattern = re.compile(r"(\w+)\s*\(([^)]*)\)")

	tool_calls = []
	for text_block in strings_to_search:
		if not isinstance(text_block, str):
			continue

		for match in call_pattern.finditer(text_block):
			function_name, arg_string = match.groups()
			try:
				# This is the fix: Use the robust AST-based parser.
				arguments_dict = _parse_arguments(arg_string)

				function_obj = {
					"name": function_name,
					"arguments": arguments_dict
				}
				tool_call_obj = {
					"function": function_obj,
					"type": 'function',
					"id": f"call_{uuid.uuid4().hex}"
				}
				tool_calls.append(tool_call_obj)
			except Exception as e:
				print(f"Could not process call for function '{function_name}': {e}")
				continue

	return tool_calls









