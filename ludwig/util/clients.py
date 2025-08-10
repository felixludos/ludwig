import openai

from .imports import *
from .abstract import AbstractClient
from .files import repo_root, hash_str
# from ..util.tools import parse_pythonic_tool_calls, parse_json_tool_calls
from ..util.parsers import AbstractParser, MessageParser

# from openai.types.chat import ChatCompletionMessage

CHAT = List[Dict[str, JSONDATA]]
REQUEST_PARAMS = Dict[str, JSONDATA]
REQUEST = JSONOBJ
RESPONSE = JSONOBJ
# RESPONSE = openai.ChatCompletion

class ClientBase(fig.Configurable, AbstractClient):
	def __init__(self, raise_length_limit: bool = True, system_message: str = None,
				 message_parser: AbstractParser = None, debug_log: bool = False, **kwargs):
		if message_parser is None:
			message_parser = MessageParser()
		super().__init__(**kwargs)
		self.system_message = system_message
		self._raise_length_limit = raise_length_limit
		self._model_name = None
		self.history = None
		self._last_response = None
		self._message_parser = message_parser
		self._debug_log = debug_log
		if self._debug_log:
			path = repo_root()/ 'client_debug_log.txt'
			with path.open('w') as f: f.write('')

	@property
	def model_name(self) -> str: # fallback
		return self.ident

	def begin_chat(self, prompt: str = None, *, role: str = 'user') -> CHAT:
		chat = [] if self.system_message is None else [{'role': 'system', 'content': self.system_message}]
		if prompt is not None:
			chat.append({'role': role, 'content': prompt})
		return chat

	def get_response(self, prompt: Union[str, CHAT], **params: JSONDATA) -> str:
		resp = self.step(self.begin_chat(prompt) if isinstance(prompt, str) else prompt, **params)
		return self.extract_response(resp)

	def wrap_prompt(self, prompt: str, params: REQUEST_PARAMS = {}) -> REQUEST:
		return self.wrap_chat(self.begin_chat(prompt), params)

	def wrap_chat(self, chat: CHAT, params: REQUEST_PARAMS = {}) -> REQUEST:
		raise NotImplementedError

	def multi_turn(self, chat: CHAT, params: REQUEST_PARAMS = {}, *, max_retries: int = None) -> Iterator[RESPONSE]:
		"""
		Input should be something like [{'role': 'user', 'content': '[prompt]'}]
		:param chat:
		:param params:
		:param max_retries:
		:return:
		"""
		assert isinstance(chat, list), f'Expected a list of messages, got {type(chat)}'

		i = 0
		while max_retries is None or i <= max_retries:
			resp = self.step(chat, **params)
			yield resp
			role = resp['choices'][0]['message']['role']
			assert chat[-1]['role'] != role, f'Chat must be updated with a new message from the user'
			i += 1

	def step(self, chat: CHAT, **params) -> RESPONSE:
		"""sends a single request"""
		if isinstance(chat, str):
			chat = self.begin_chat(chat)

		data = self.wrap_chat(chat, params)
		if data.get('n', 1) > 1:
			print(f'WARNING: Multiple responses is unsupported: {data["n"]} responses requested')

		resp = self.send(data)
		# assert len(resp.choices) > 1, f'Expected one response, got {len(resp.choices)} choices'

		if self._raise_length_limit and resp['choices'][0]['finish_reason'] == 'length':
			raise BudgetExceededError(f'Response length limit reached {resp["usage"]["completion_tokens"]} tokens '
									  f'(try increasing `max_tokens`)', resp)

		input_length = len(chat)

		# update chat with the response
		msg = resp['choices'][0]['message']
		assistant_turn = {'role': msg['role']}
		assistant_turn['content'] = msg['content']
		if msg.get('tool_calls'):
			assistant_turn['tool_calls'] = resp['choices'][0]['message'].get('tool_calls', [])
		chat.append(assistant_turn)

		# extract additional chat relevant info
		extra_info = resp['choices'][0].get('model_extra', {})
		if extra_info is not None and extra_info.get('reasoning_content'):
			chat[-1]['reasoning_content'] = extra_info['reasoning_content']

		return resp

	def stream_response(self, prompt: Union[str, List[Dict[str, str]]], **params) -> Iterator[str]:
		if isinstance(prompt, str):
			prompt = self.wrap_prompt(prompt, **params)
		else:
			prompt = self.wrap_chat(prompt, **params)
		for resp in self.send_no_wait(prompt):
			yield self.extract_response(resp)

	def _record_send(self, data: JSONOBJ):
		pass

	def _record_send_no_wait(self, data: JSONOBJ):
		self._record_send(data)

	def _record_response(self, data: JSONOBJ, resp: JSONOBJ):
		pass

	def _record_step(self, data: JSONOBJ, step: JSONOBJ):
		pass

	def json(self) -> JSONOBJ:
		return {
			'system_message': self.system_message,
		}

	def send(self, data: JSONOBJ) -> openai.ChatCompletion:
		self._record_send(data)
		resp = self._send(data)
		resp = self._post_response_fixes(data, resp)
		self._record_response(data, resp)
		return resp

	def _post_response_fixes(self, data: REQUEST_PARAMS, resp: RESPONSE) -> openai.ChatCompletion:
		"""
		Override this method to apply any post-processing fixes to the response.
		For example, to handle reasoning content or tool calls.
		"""
		msg = resp['choices'][0].get('message')
		if msg is None:
			# msg = resp['choices'][0].get('model_extra', {}).get('message')
			text = resp['choices'][0].get('text', None)
			assert text is not None, f'No text found in response: {resp}'
			msg = self._message_parser.parse(text, data, resp)
		if msg is None:
			text = resp['choices'][0].get('text')
			msg = {'role': 'assistant', 'content': text, 'tool_calls': []}
		assert msg is not None, f'No message found in response: {resp}'
		if 'content' not in msg:
			msg['content'] = None
		resp['choices'][0]['message'] = msg
		# content = msg['content']

		if self._debug_log:
			path = repo_root()/ 'client_debug_log.txt'
			with path.open('a', encoding='utf-8') as f:
				N = 80
				if 'prompt' in data:
					f.write(data['prompt'] + '\n')
				if 'text' in resp['choices'][0]:
					# f.write('*'*N + '\n')
					f.write(f'*** {self.ident} ' + '*'*max(0,N-len(self.ident)-5) + '\n')
					# f.write('*'*N + '\n')
					f.write(resp['choices'][0]['text'] + '\n')
					if 'tool_calls' in msg and len(msg['tool_calls']):
						tcalls = msg["tool_calls"]
						# payload = yaml.dump(data, default_flow_style=None, sort_keys=False)
						# payload = json.dumps(msg["tool_calls"], indent=2)
						payload = '\n'.join(json.dumps(tc) for tc in tcalls)
						payload = payload.replace("\n", "\n| ")
						f.write(f'| Tool calls ({len(tcalls)}): \n| {payload}\n')
				if 'prompt' in data or 'text' in resp['choices'][0]:
					f.write(('*'*N + '\n')*2)

		return resp

	def _send(self, data: JSONOBJ) -> openai.ChatCompletion:
		raise NotImplementedError

	def send_no_wait(self, data: JSONOBJ) -> Iterator[JSONOBJ]:
		self._record_send_no_wait(data)
		for resp in self._send_no_wait(data):
			self._record_step(data, resp)
			yield resp

	def _send_no_wait(self, data: JSONOBJ) -> Iterator[JSONOBJ]:
		raise NotImplementedError



@fig.component('mock')
class MockEndpoint(ClientBase):
	def __init__(self, *, responses: List[str] = None, **kwargs):
		if responses is None:
			responses = []
		super().__init__(**kwargs)
		self.responses = list(reversed(responses))
		self.history = []
		self._last_response = None

	def prepare(self) -> 'Self':
		self.history = []
		self._last_response = None
		return self

	@property
	def ident(self) -> str:
		return 'mock'

	def ping(self) -> bool:
		return True

	def past_requests(self) -> int:
		return len(self.history)

	def stats(self, starting_from: int = 0) -> JSONOBJ:
		return {
			'input_tokens': sum(h['input_tokens'] for h in self.history[starting_from:]),
			'output_tokens': sum(h['output_tokens'] for h in self.history[starting_from:]),
			'requests': len(self.history[starting_from:]),
		}

	def _record_send(self, data: JSONOBJ):
		self.history.append({'input_tokens': self.count_tokens(data['chat']), 'start_time': time.time()})
		self._last_response = []

	def _record_response(self, data: JSONOBJ, resp: JSONOBJ):
		self.history[-1].update({
			'output_tokens': self.count_tokens(resp['response']),
			'end_time': time.time(),
		})
		self._last_response = [resp['response']]

	def _record_step(self, data: JSONOBJ, step: JSONOBJ):
		if 'output_tokens' not in self.history[-1]:
			self.history[-1]['output_tokens'] = 0
		self.history[-1]['output_tokens'] += 1
		self._last_response.append(step['response'])

	def last_response(self) -> str:
		if self._last_response is not None:
			return ' '.join(self._last_response)

	def count_tokens(self, message: Union[str, List[Dict[str, str]]]) -> int:
		if isinstance(message, str):
			return len(message.split())
		return sum(self.count_tokens(m['content']) for m in message)

	def wrap_chat(self, chat: List[Dict[str, str]], **params) -> JSONOBJ:
		return {'chat': chat}

	def extract_response(self, data):
		return data['response']

	def _send(self, data: JSONOBJ) -> JSONOBJ:
		assert 'chat' in data
		chat = data['chat']
		return {'response': self.responses.pop() if len(self.responses)
				else f'This is the mock response to a chat with {len(chat)} messages.'}

	def _send_no_wait(self, data):
		resp = self._send(data)
		for token in resp['response'].split():
			time.sleep(0.03)
			yield {'response': token}



class OpenaiClientBase(ClientBase):
	def __init__(self, endpoint: Union[openai.OpenAI, str], *, max_tokens: int = None, seed: int = None,
				 temperature: float = None, top_p: float = None, grammar: Union[str, JSONOBJ] = None,
				 **kwargs):
		if isinstance(endpoint, str):
			endpoint = openai.OpenAI(api_key='EMPTY', base_url=endpoint)
		super().__init__(**kwargs)
		self.endpoint = endpoint

		self.max_tokens = max_tokens
		self.temperature = temperature
		self.top_p = top_p
		self.seed = seed
		self.grammar = grammar

		self._tokenizer = None
		# self._chat_template = chat_template

	@property
	def ident(self) -> str:
		if self._model_name is None:
			return f'{self.endpoint.base_url}'
		name = self._model_name
		if 'hub/models--' in name:
			name = name.split('hub/models--')[-1].split('/')[0].replace('--', '/')
		return name

	def prepare(self) -> 'Self':
		self.history = []
		try:
			import tiktoken
		except ImportError:
			tokenizer = None
		else:
			tokenizer = tiktoken.get_encoding("cl100k_base")
		self._tokenizer = tokenizer
		self._last_response = None

	def json(self) -> JSONOBJ:
		info = {
			'base_url': str(self.endpoint.base_url),
			'model_name': self._model_name,
			'max_tokens': self.max_tokens,
			'temperature': self.temperature,
			'top_p': self.top_p,
			'seed': self.seed,
			**super().json()
		}
		if self.grammar is not None:
			info['grammar'] = self.grammar
		return info

	def past_requests(self) -> int:
		return len(self.history)

	def stats(self, starting_from: int = 0) -> JSONOBJ:
		def _metrics(seq: Sequence[float]):
			if len(seq) == 1:
				return seq[0]
			return {'mean': sum(seq) / len(seq), 'min': min(seq), 'max': max(seq),}
		data = {}
		times = [h.get('end_time',0) - h.get('start_time',0) for h in self.history[starting_from:] if 'end_time' in h]
		if times:
			tps = [h['output_tokens']/(h['end_time'] - h['start_time'])
				   for h in self.history[starting_from:] if 'end_time' in h]
			data['time'] = _metrics(times)
			data['tok_per_sec'] = _metrics(tps)
		summary = {
			'input_tokens': sum(h.get('input_tokens',0) for h in self.history[starting_from:]),
			'output_tokens': sum(h.get('output_tokens',0) for h in self.history[starting_from:]),
			**data,
			'requests': len(self.history[starting_from:]),
		}
		return summary

	def count_tokens(self, message: Union[str, List[Dict[str, str]]]) -> int:
		return 0 # because of mistral
		if self._tokenizer is None:
			return 0
		if isinstance(message, str):
			return len(self._tokenizer.encode(message))
		return sum(len(self._tokenizer.encode(m['content'])) for m in message if 'content' in m)

	@staticmethod
	def _include_grammar(args: JSONOBJ):
		if 'grammar' in args:
			raise NotImplementedError

	_valid_chat_keys = {'role', 'content', 'name', 'function_call', 'tool_calls', 'tool_call_id'}
	def wrap_chat(self, chat: CHAT, params: REQUEST_PARAMS = None) -> JSONOBJ:
		# for m in chat:
		# 	assert all(k in self._valid_chat_keys for k in m), f'Invalid keys in chat message: {m.keys()}'
		messages = [{key: val for key, val in m.items() if key in self._valid_chat_keys} for m in chat]
		if self.max_tokens is None and (params is None or 'max_tokens' not in params):
			print(f'WARNING: `max_tokens` cannot be None, setting to 2048 for now.')
			self.max_tokens = 2048
		args = {'messages': messages, 'model': self._model_name, 'max_tokens': self.max_tokens,
				# 'do_sample': self.temperature is not None or self.top_p is not None,
			 'temperature': self.temperature, 'top_p': self.top_p, 'seed': self.seed}
		if self.grammar is not None:
			args['extra_body'] = self.grammar
		if params is not None:
			args.update(params)
		self._include_grammar(args)
		return args

	def extract_response(self, data: JSONOBJ) -> str:
		content = data['choices'][0]['message'].get('content', None)
		if content is None and 'reasoning_content' in data['choices'][0]['message'].get('model_extra', {}):
			return data['choices'][0]['message']['model_extra']['reasoning_content']
		return content

	def last_response(self) -> Optional[str]:
		if self._last_response is not None:
			return self._last_response
		return None

	def _send(self, data: JSONOBJ) -> RESPONSE:
		return self.endpoint.chat.completions.create(**data).model_dump()

	def _send_no_wait(self, data):
		for chunk in self.endpoint.chat.completions.create(
				**data, stream=True, stream_options={"include_usage": True}):
			yield chunk.model_dump()

	def stream_response(self, prompt: Union[str, List[Dict[str, str]]], **params) -> Iterator[str]:
		if isinstance(prompt, str):
			prompt = self.wrap_prompt(prompt, **params)
		else:
			prompt = self.wrap_chat(prompt, **params)
		for resp in self.send_no_wait(prompt):
			if len(resp['choices']):
				yield resp['choices'][0]['delta'].get('content', '')

	def _record_send(self, data: JSONOBJ):
		self._last_response = ''
		self.history.append({})
		if self._tokenizer is not None:
			self.history[-1]['estimated_input_tokens'] = self.count_tokens(data['messages'])
		self.history[-1]['start_time'] = time.time()

	def _record_response(self, data: JSONOBJ, resp: RESPONSE):
		N_inp = resp['usage'].get('prompt_tokens', 0)
		N_out = resp['usage'].get('completion_tokens', 0)
		stats = {
			'input_tokens': N_inp,
			'output_tokens': N_out,
			'end_time': time.time(),
		}
		self._last_response = resp['choices'][0]['message'].get('content', '')
		self.history[-1].update(stats)

	def _record_step(self, data: JSONOBJ, step: RESPONSE):
		if len(step['choices']):
			self._last_response += step['choices'][0]['delta'].get('content', '')
		if step['usage'] is not None:
			self.history[-1]['input_tokens'] = step['usage']['prompt_tokens']
			self.history[-1]['output_tokens'] = step['usage']['completion_tokens']
			self.history[-1]['end_time'] = time.time()

	def ping(self) -> bool:
		return True # TODO: implement a ping method for OpenAI endpoints

	def __str__(self):
		return self.ident



@fig.component('vllm')
class vllm_Client(OpenaiClientBase):
	def __init__(self, addr: Union[str, int], *, use_chat_completion: bool = False, tool_style: str = 'pythonic',
				 chat_template_path: Optional[str] = None, chat_template: Optional[str] = None,
				 enable_thinking: bool = False,
				 add_generation_prompt: bool = True, continue_final_message: bool = False, **kwargs):
		assert tool_style in (None, 'pythonic', 'json')
		assert chat_template_path is None or chat_template is None, \
			f'Cannot specify both chat_template_path and chat_template'
		if use_chat_completion:
			raise NotImplementedError(f'Not supported (anymore)')
		super().__init__(endpoint=self._to_full_addr(addr), **kwargs)
		self._add_generation_prompt = add_generation_prompt
		self._continue_final_message = continue_final_message
		self._chat_template_path = chat_template_path
		self._chat_template = chat_template
		self._use_chat = use_chat_completion
		self._tool_style = tool_style
		self._enable_thinking = enable_thinking

	def json(self) -> JSONOBJ:
		info = super().json()
		info['addr'] = str(self.endpoint.base_url)
		info['add_generation_prompt'] = self._add_generation_prompt
		info['continue_final_message'] = self._continue_final_message
		info['chat_template_path'] = None if self._chat_template_path is None else str(self._chat_template_path)
		if self._chat_template_path is None and self._chat_template is not None:
			info['chat_template'] = self._chat_template
		if self._chat_template_path is not None:
			info['tool_style'] = self._tool_style
		if self.model_name is not None and self.model_name.startswith('Qwen/'):
			info['enable_thinking'] = self._enable_thinking
		return info

	@staticmethod
	def _to_full_addr(addr: Union[str, int]) -> str:
		addr = str(addr)
		if addr.startswith('http'):
			if addr.endswith('v1/'):
				return addr
			elif addr.endswith('/'):
				return f'{addr}v1'
			elif addr.endswith('/v1'):
				return addr
			return f'{addr}/v1'
		if ':' in addr:
			return f'http://{addr}/v1'
		assert addr.isdigit(), f'{addr} is not a valid port number'
		return f'http://localhost:{addr}/v1'

	def _server_model_info(self) -> JSONOBJ:
		try:
			response = requests.get(str(self.endpoint.base_url.join('models')))
			response.raise_for_status()  # Raise an error for bad responses
			model_info = response.json()
			return model_info
		except requests.RequestException as e:
			print(f"Error fetching model info: {e}")
			return {}

	def _send(self, data: JSONOBJ) -> RESPONSE:
		if self._tokenizer is None:
			return super()._send(data)

		tools, docs = data.pop('tools', None), data.pop('documents', None)
		data.pop('tool_choice', None)
		chat = data.pop('messages', None)
		if chat is not None:

			tok_args = {
				'tokenize': False,
				'tools': tools,
				'documents': docs,
				'add_generation_prompt': self._add_generation_prompt,
				'continue_final_message': self._continue_final_message,
				'chat_template': self._chat_template,
			}
			if 'qwen' in self.model_name.lower():
				tok_args['enable_thinking'] = self._enable_thinking
			try:
				prompt = self._tokenizer.apply_chat_template(chat, **tok_args)

			except Exception:
				# pretty print
				print(f'Error applying chat template for {self.ident} with chat:')
				print(chat)

				print(f'Using Chat template: {self._chat_template_path}')
				print(self._chat_template)
				raise

			data['prompt'] = prompt

		# print(data)
		resp = self.endpoint.completions.create(**data).model_dump()

		if tools is not None:
			data['tools'] = tools
		if docs is not None:
			data['documents'] = docs
		if chat is not None:
			data['messages'] = chat
		return resp

	def _build_tokenizer(self, model_name: str, *, trust_remote_code: bool = True, **kwargs) -> 'AutoTokenizer':
		"""
		Builds a tokenizer for the specified model.
		:param model_name: The name of the model to build the tokenizer for.
		:param trust_remote_code: Whether to trust remote code when loading the tokenizer.
		:return: An instance of AutoTokenizer.
		"""
		name = model_name.lower()

		if 'mistral' in name:
			from mistral_common.tokens.tokenizers.mistral import MistralTokenizer
			tokenizer = MistralTokenizer.from_hf_hub(model_name)
			return tokenizer

		from transformers import AutoTokenizer
		if ('phi' in name and 'microsoft' in model_name) \
			or ('tencent' in name and 'hunyuan' in model_name):
			return AutoTokenizer.from_pretrained(model_name, trust_remote_code=True, **kwargs)

		return AutoTokenizer.from_pretrained(model_name, **kwargs)

	_default_chat_template = '{root}/tools-{tool_style}/{model_name}.jinja'
	def prepare(self) -> 'Self':
		super().prepare()
		# info = self.endpoint.models.list()
		# self._model_name = info.data[0].id
		info = self._server_model_info()
		self._model_name = info['data'][0]['id']
		# self._max_model_len = info['data'][0].get('max_model_len', None)
		# if self.max_tokens is None:
		# 	self.max_tokens = self._max_model_len
		# if self._chat_template is not None:
		# 	self._chat_template.prepare(self._model_name)

		try:
			if self._use_chat:
				self._tokenizer = None
			else:
				try:
					self._tokenizer = self._build_tokenizer(self.ident)
				except:
					try:
						self._tokenizer = self._build_tokenizer(self._model_name)
					except:
						print(f'Tokenizer not found for both {self.ident} and {self._model_name}')
						raise
					else:
						print(f'NOTE: Built tokenizer using: {self._model_name}')

		except:
			if not self._use_chat:
				raise
			self._tokenizer = None
		else:
			# self._tokenizer.jinja_env.filters['fromjson'] = json.loads
			chat_template_path = self._chat_template_path
			if not self._use_chat and self._chat_template is None and self._chat_template_path is None:
				chat_template_path = self._default_chat_template
			if self._chat_template is None and chat_template_path is not None:
				path = chat_template_path
				root = repo_root().joinpath('assets', 'chat-template')
				path = Path(pformat(path, root=root, model_name=self.ident, tool_style=self._tool_style))
				if not path.exists():
					if self._chat_template_path is not None:
						raise FileNotFoundError(f'Chat template not found: {path}')
					else:
						print(f'WARNING: Default chat template not found at {path}')
				else:
					self._chat_template_path = path
					template = path.read_text()
					self._chat_template = template
		return self

	def ping(self) -> bool:
		try:
			url = self.endpoint.base_url
			print(f'Pinging endpoint {url}')
			response = requests.get(f"{str(url).replace(url.path, '')}/ping")
			response.raise_for_status()
			return response.status_code == 200
		except requests.RequestException as e:
			print(f"Error pinging server: {e}")
			return False

	@staticmethod
	def _include_grammar(args: JSONOBJ):
		if 'grammar' in args:
			grammar = args['grammar']
			if isinstance(grammar, str):
				grammars = {'yes/no': {"guided_choice": ["yes", "no"]},
							'yes/no/unknown': {"guided_choice": ["yes", "no", "unknown"]},
							'pos/neg': {"guided_choice": ["positive", "negative"]},
							'mcq4': {"guided_choice": ["A", "B", "C", "D"]}}
				if grammar not in grammars:
					raise ValueError(f'Unknown grammar: {grammar}')
				grammar = grammars[grammar]
			# TODO: check if grammar is valid
			elif isinstance(grammar, dict):
				grammar =  {'guided_json': grammar}
			elif isinstance(grammar, list):
				grammar = {'guided_choice': grammar}
			args['extra_body'] = grammar
			del args['grammar']



@fig.component('openai')
class Openai_Client(OpenaiClientBase):
	@fig.silent_config_args('api_key')
	def __init__(self, model_name: str = None, *, api_key: str, **kwargs):
		super().__init__(endpoint=openai.OpenAI(api_key=api_key), **kwargs)
		self._model_name = model_name

	def available_models(self) -> JSONOBJ:
		"""
		Returns a list of available models from the OpenAI API.
		"""
		response = self.endpoint.models.list()
		return response.to_dict()['data']

	def _clean_schema(self, schema: JSONDATA):
		"""because openai's grammar is weaker than vllm's"""
		if isinstance(schema, dict):
			fixed = {}
			for key, value in schema.items():
				if key not in {'minimum', 'maximum', 'minItems', 'maxItems'}:
					fixed[key] = self._clean_schema(value)
			if fixed.get('type') == 'object':
				if 'additionalProperties' in fixed and fixed['additionalProperties']:
					raise ValueError(f'Not allowed: {fixed}')
				fixed['additionalProperties'] = False
				if 'required' not in fixed:
					fixed['required'] = list(fixed.get('properties', []))
			return fixed
		if isinstance(schema, list):
			return [self._clean_schema(item) for item in schema]
		return schema

	def _include_grammar(self, args: JSONOBJ):
		if 'grammar' in args:
			grammar = args['grammar']
			if isinstance(grammar, str):
				raise NotImplementedError
				grammars = {'yes/no': {"guided_choice": ["yes", "no"]},
							'yes/no/unknown': {"guided_choice": ["yes", "no", "unknown"]},
							'pos/neg': {"guided_choice": ["positive", "negative"]},
							'mcq4': {"guided_choice": ["A", "B", "C", "D"]}}
				if grammar not in grammars:
					raise ValueError(f'Unknown grammar: {grammar}')
				grammar = grammars[grammar]
			# TODO: check if grammar is valid
			if isinstance(grammar, dict):
				if grammar.get('type') != 'object':
					grammar = {'type': 'object', 'properties': {'data': grammar}}
				fixed = self._clean_schema(grammar)
				args['response_format'] = {'json_schema': {"name": "my_schema", "strict": True, "schema": fixed},
										   'type': 'json_schema'}
			del args['grammar']



@fig.component('azure')
class OpenaiAzure_Client(OpenaiClientBase):
	@fig.silent_config_args('api_key')
	def __init__(self, model_name: str, *, api_base: str, api_key: str, api_version: str, **kwargs):
		endpoint = openai.AzureOpenAI(azure_endpoint=api_base, api_key=api_key, api_version=api_version)
		super().__init__(endpoint=endpoint, **kwargs)
		self._model_name = model_name


@fig.modifier('logged')
class Logged(ClientBase):
	_default_request_log_root = repo_root().joinpath('requests')
	def __init__(self, log_request: str = '{str(n).zfill(4)}_request', log_response: str = '{str(n).zfill(4)}_response',
				 log_dir: str = '{"azure" if "azure" in client.__class__.__name__.lower() else '
								'"vllm" if "vllm" in client.__class__.__name__.lower() else "openai"}'
								'_{now.strftime("%y%m%d-%H%M%S")}_{unique[:4]}', log_root: Path = _default_request_log_root,
				 no_log: bool = False, **kwargs):
		log_root = Path(log_root)
		super().__init__(**kwargs)
		self._active = not no_log
		self._log_request_fmt = log_request
		self._log_response_fmt = log_response
		self._log_root = log_root
		self._log_dir_fmt = log_dir
		self._log_dir = None
		self._codes = {}
		self._num_requests = 0
		now = datetime.now()
		self._timestamp = now.strftime('%y%m%d-%H%M%S')

	def prepare(self) -> 'Self':
		out = super().prepare()
		if self._active:
			self._log_dir = self._log_root / pformat(self._log_dir_fmt, client=self, now=datetime.now(),
													 unique=urandom(16).hex())
			self._log_dir.mkdir(parents=False, exist_ok=False)
			json.dump(self.json(), self._log_dir.joinpath('client.json').open('w'), indent=2)
		return out

	def json(self) -> JSONOBJ:
		data = super().json()
		if self._active:
			data['log-dir'] = str(self._log_dir)
		return data

	def _log_request(self, payload: str):
		n = self._num_requests
		path = self._log_dir / pformat(self._log_request_fmt, client=self, now=datetime.now(), n=n, str=str)
		# path = self._log_dir / self._log_request_fmt.format(client=self, now=datetime.now(), n=n, str=str)
		if path.suffix != '.json':
			path = path.with_suffix('.json')
		path.write_text(payload, encoding='utf-8')
		self._codes[hash(payload)] = self._num_requests
		self._num_requests += 1

	def _record_send(self, data: JSONOBJ):
		if self._active:
			payload = json.dumps(data, indent=2)
			self._log_request(payload)
		return super()._record_send(data)

	def _record_response(self, data: JSONOBJ, resp: JSONOBJ):
		if self._active:
			payload = json.dumps(data, indent=2)
			if hash(payload) not in self._codes:
				self._log_request(payload)
			n = self._codes.pop(hash(payload))
			path = self._log_dir / pformat(self._log_response_fmt, client=self, now=datetime.now(), n=n, str=str)
			if path.suffix != '.json':
				path = path.with_suffix('.json')
			# path = self._log_dir / self._log_response_fmt.format(client=self, now=datetime.now(), n=n, str=str)
			# resp_data = resp.json()
			path.write_text(json.dumps(resp), encoding='utf-8')
		return super()._record_response(data, resp)



class Tool_Client(ClientBase):
	def __init__(self, tools: Union[Dict[str, AbstractTool], Iterable[AbstractTool]] = None, **kwargs):
		if tools is None:
			tools = []
		elif isinstance(tools, dict):
			tools = tools.values()
		super().__init__(**kwargs)
		self.tools = {t.name: t for t in tools}

	def _record_response(self, data: JSONOBJ, resp: RESPONSE):
		super()._record_response(data, resp)
		if resp['choices'][0]['message'].get('tool_calls'):
			self.history[-1]['tool_calls'] = dict(Counter(call['function']['name'] for call in resp['choices'][0]['message']['tool_calls']))

	def stream_response(self, prompt: Union[str, List[Dict[str, str]]], **params) -> Iterator[str]:
		if self.tools:
			# see: https://docs.vllm.ai/en/v0.6.3.post1/getting_started/examples/openai_chat_completion_client_with_tools.html
			raise NotImplementedError
		return super().stream_response(prompt, **params)

	def wrap_chat(self, chat: CHAT, params: REQUEST_PARAMS) -> RESPONSE:
		args = super().wrap_chat(chat, params)
		if self.tools:
			args['tools'] = [tool.schema() for tool in self.tools.values()]
		return args

	def stats(self, starting_from: int = 0) -> JSONOBJ:
		summary = super().stats(starting_from=starting_from)
		if any('tool_calls' in h for h in self.history[starting_from:]):
			tool_calls = Counter()
			for h in self.history[starting_from:]:
				if 'tool_calls' in h:
					tool_calls.update(h['tool_calls'])
			summary['tool_calls'] = dict(tool_calls)
		return summary

	def json(self) -> JSONOBJ:
		data = super().json()
		if self.tools:
			data['tools'] = [tool.json() for tool in self.tools.values()]
		return data

	def register_tools(self, *tools: AbstractTool) -> 'Self':
		for tool in tools:
			self.tools[tool.name] = tool
		return self

	def json(self) -> JSONOBJ:
		info = super().json()
		if self.tools:
			info['tools'] = [tool.json() for tool in self.tools.values()]
		return info

	def resolve_tool_calls(self, chat: CHAT) -> List[Dict[str, str]]:
		tool_results = []
		for item in reversed(chat):
			if 'tool_calls' in item:
				for tool_call in item['tool_calls']:
					info = tool_call['function']
					assert info['name'] in self.tools, f'Tool {info["name"]} not registered'
					tool = self.tools[info['name']]
					arguments = info['arguments']
					if isinstance(arguments, str):
						arguments = json.loads(arguments)
					try:
						result = tool.call(arguments)
					except ToolError as e:
						result = str(e) if type(e) == ToolError else f'{e.__class__.__name__}: {e}'
					tool_results.append({'role': 'tool',
										 'content': result,
										 'tool_call_id': tool_call['id'],
										 'name': info['name']})
			else:
				break
		tool_results = list(reversed(tool_results))
		chat.extend(tool_results)
		return tool_results


	def step(self, chat: CHAT, auto_tool_rounds: Optional[int] = None, **params) -> RESPONSE:
		resp = super().step(chat, **params)
		self.resolve_tool_calls(chat)
		if (auto_tool_rounds is None or auto_tool_rounds >= 0) and chat[-1].get('role') == 'tool':
			return self.step(chat, auto_tool_rounds=None if auto_tool_rounds is None else auto_tool_rounds-1, **params)
		return resp


class Local_vllm_Client(ClientBase):
	def __init__(self, model_name: str, *, max_tokens: int = None, seed: int = None,
				 temperature: float = None, top_p: float = None, **kwargs):
		super().__init__(**kwargs)
		raise NotImplementedError(f'todo')
		self._model_name = model_name
		self.max_tokens = max_tokens
		self.temperature = temperature
		self.top_p = top_p
		self.seed = seed

		self._tokenizer = None
		self.history = None
		self._model_name = None
		self._last_response = None



# Completion(id='cmpl-9f402c1a31004efdba6df3c46bfb81ec', choices=[
# 	CompletionChoice(finish_reason='length', index=0, logprobs=None,
# 					 text=' city in _____. Multiple choice:\na. California\nb. New York\n', stop_reason=None,
# 					 prompt_logprobs=None)], created=1743710032, model='microsoft/Phi-4-multimodal-instruct',
# 		   object='text_completion', system_fingerprint=None,
# 		   usage=CompletionUsage(completion_tokens=16, prompt_tokens=8, total_tokens=24,
# 								 completion_tokens_details=None, prompt_tokens_details=None))

# ChatCompletion(id='chatcmpl-db823bf039a64989b0514e7dd29c52e9', choices=[
# 	Choice(finish_reason='stop', index=0, logprobs=None, message=
# 	ChatCompletionMessage(content='Why was the math book sad?\n\nBecause it had too many problems! 😄',
# 						  refusal=None, role='assistant', annotations=None, audio=None, function_call=None,
# 						  tool_calls=[], reasoning_content=None), stop_reason=200020)],
# 			   created=1743710209, model='microsoft/Phi-4-multimodal-instruct', object='chat.completion',
# 			   service_tier=None, system_fingerprint=None, usage=
# 			   CompletionUsage(completion_tokens=17, prompt_tokens=9, total_tokens=26,
# 							   completion_tokens_details=None, prompt_tokens_details=None), prompt_logprobs=None)

# ChatCompletionChunk(id='chatcmpl-df89efcca98343b5aed4f11a267bcd5a', choices=[
# 	Choice(delta=ChoiceDelta(content='', function_call=None, refusal=None, role='assistant', tool_calls=None),
# 		   finish_reason=None, index=0, logprobs=None)], created=1743711902,
# 					model='microsoft/Phi-4-multimodal-instruct', object='chat.completion.chunk', service_tier=None,
# 					system_fingerprint=None, usage=None)

# from .files import repo_root
# try:
# 	import jinja2
# except ImportError:
# 	jinja2 = None


# class ChatTemplate:
# 	_default_path = '{root}/chat-template/default.jinja'
# 	def __init__(self, *, use_default: bool = False, chat_style: Optional[str] = None,
# 				 add_generation_prompt: bool = True,
# 				 template_path: str = '{root}/chat-template/{model_name.replace("/", "--")}.jinja', **kwargs):
# 		super().__init__(**kwargs)
# 		self._model_name = None
# 		if isinstance(use_default, str):
# 			self._default_path = use_default
# 		self._use_default = use_default
# 		self._template_path = template_path
# 		self._template = None
# 		self._root = repo_root().joinpath('assets')
# 		if chat_style is None:
# 			self._root = self._root.joinpath(chat_style)
# 			assert self._root.exists(), f'Chat style root does not exist: {self._root}'
# 		self._add_generation_prompt = add_generation_prompt
#
# 	def prepare(self, model_name: str):
# 		self._model_name = model_name
#
# 		if jinja2 is None:
# 			path = pformat(self._template_path, assets_path=, model_name=model_name)
# 			path = Path(path)
#
# 			if not path.exists():
# 				if self._use_default:
# 					path = pformat(self._default_path, assets_path=repo_root().joinpath('assets'))
# 					path = Path(path)
# 				else:
# 					raise FileNotFoundError(path)
#
# 			self._template = path.read_text()
# 		return self
#
# 	def fill(self, chat: CHAT, **kwargs) -> Optional[str]:
# 		if self._template is None:
# 			return None
# 		template = jinja2.Template(self._template)#, trim_blocks=True, lstrip_blocks=True)
# 		formatted_prompt = template.render(
# 			messages=chat,
# 			add_generation_prompt=self._add_generation_prompt,
# 			**kwargs
# 		)
# 		return formatted_prompt



