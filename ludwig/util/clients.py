import openai

from .imports import *
from .abstract import AbstractClient


class ClientBase(fig.Configurable, AbstractClient):
	def wrap_prompt(self, prompt: str, **params) -> JSONOBJ:
		return self.wrap_chat([{'role': 'user', 'content': prompt}], **params)

	def get_response(self, prompt: Union[str, List[Dict[str, str]]], **params) -> str:
		if isinstance(prompt, str):
			prompt = self.wrap_prompt(prompt, **params)
		else:
			prompt = self.wrap_chat(prompt, **params)
		full = self.send(prompt)
		return self.extract_response(full)

	def wrap_chat(self, chat: List[Dict[str, str]], **params) -> JSONOBJ:
		raise NotImplementedError

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
		return {}

	def send(self, data: JSONOBJ) -> JSONOBJ:
		self._record_send(data)
		resp = self._send(data)
		self._record_response(data, resp)
		return resp

	def _send(self, data: JSONOBJ) -> JSONOBJ:
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
	def prepare(self) -> Self:
		self.history = []
		self._last_response = None
		return self

	@property
	def ident(self) -> str:
		return 'mock'

	def ping(self) -> bool:
		return True

	def stats(self) -> JSONOBJ:
		return {
			'input_tokens': sum(h['input_tokens'] for h in self.history),
			'output_tokens': sum(h['output_tokens'] for h in self.history),
			'requests': len(self.history),
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
		return {'response': f'This is the mock response to a chat with {len(chat)} messages.'}

	def _send_no_wait(self, data):
		resp = self._send(data)
		for token in resp['response'].split():
			time.sleep(0.03)
			yield {'response': token}



@fig.component('vllm')
class vllm_Client(ClientBase):
	def __init__(self, addr: str, *, max_tokens: int = None, temperature: float = None, top_p: float = None,
				 seed: int = None, **kwargs):
		super().__init__(**kwargs)
		self.addr = self._to_full_addr(addr)
		self.max_tokens = max_tokens
		self.temperature = temperature
		self.top_p = top_p
		self.seed = seed
		self._client = None
		self._tokenizer = None
		self.history = None
		self._model_name = None
		self._last_response = None

	@staticmethod
	def _to_full_addr(addr: str) -> str:
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

	@property
	def ident(self) -> str:
		return f'{self.addr}'

	def _server_model_info(self) -> JSONOBJ:
		try:
			response = requests.get(f"{self.addr}/models")
			response.raise_for_status()  # Raise an error for bad responses
			model_info = response.json()
			return model_info
		except requests.RequestException as e:
			print(f"Error fetching model info: {e}")
			return {}

	def prepare(self) -> Self:
		self.history = []
		try:
			import tiktoken
		except ImportError:
			tokenizer = None
		else:
			tokenizer = tiktoken.get_encoding("cl100k_base")
		self._tokenizer = tokenizer
		self._last_response = None

		self._model_name = self._server_model_info()['data'][0]['id']

		self._client = openai.OpenAI(api_key='EMPTY', base_url=self.addr)

		return self

	def ping(self) -> bool:
		try:
			response = requests.get(f"{self.addr[:-3]}/ping")
			response.raise_for_status()
			return response.status_code == 200
		except requests.RequestException as e:
			print(f"Error pinging server: {e}")
			return False

	def json(self) -> JSONOBJ:
		return {
			'addr': self.addr,
			'model-name': self._model_name,
			'max_tokens': self.max_tokens,
			'temperature': self.temperature,
			'top_p': self.top_p,
			'seed': self.seed,
			**super().json()
		}

	def stats(self) -> JSONOBJ:
		def _metrics(seq: Sequence[float]):
			return {'mean': sum(seq) / len(seq), 'min': min(seq), 'max': max(seq),}
		data = {}
		times = [h['end_time'] - h['start_time'] for h in self.history if 'end_time' in h]
		if times:
			tps = [h['output_tokens']/(h['end_time'] - h['start_time']) for h in self.history if 'end_time' in h]
			data['time'] = _metrics(times)
			data['tok_per_sec'] = _metrics(tps)
		return {
			'input_tokens': sum(h['input_tokens'] for h in self.history),
			'output_tokens': sum(h['output_tokens'] for h in self.history),
			**data,
			'requests': len(self.history),
		}

	def count_tokens(self, message: Union[str, List[Dict[str, str]]]) -> int:
		if self._tokenizer is None:
			return 0
		if isinstance(message, str):
			return len(self._tokenizer.encode(message))
		return sum(len(self._tokenizer.encode(m['content'])) for m in message)

	def wrap_chat(self, chat: List[Dict[str, str]], **params) -> JSONOBJ:
		args = {'messages': chat, 'model': self._model_name, 'max_tokens': self.max_tokens,
			 'temperature': self.temperature, 'top_p': self.top_p, 'seed': self.seed}
		args.update(params)
		return args

	def extract_response(self, data: JSONOBJ) -> str:
		return data.choices[0].message.content

	def last_response(self) -> Optional[str]:
		if self._last_response is not None:
			return self._last_response
		return None

	def _send(self, data: JSONOBJ) -> openai.ChatCompletion:
		return self._client.chat.completions.create(**data)

	def _send_no_wait(self, data):
		for chunk in self._client.chat.completions.create(**data, stream=True, stream_options={"include_usage": True}):
			yield chunk

	def stream_response(self, prompt: Union[str, List[Dict[str, str]]], **params) -> Iterator[str]:
		if isinstance(prompt, str):
			prompt = self.wrap_prompt(prompt, **params)
		else:
			prompt = self.wrap_chat(prompt, **params)
		for resp in self.send_no_wait(prompt):
			if len(resp.choices):
				yield resp.choices[0].delta.content

	def _record_send(self, data: JSONOBJ):
		self._last_response = ''
		self.history.append({'estimated_input_tokens': self.count_tokens(data['messages']), 'start_time': time.time()})

	def _record_response(self, data: JSONOBJ, resp: openai.ChatCompletion):
		N_inp = resp.usage.prompt_tokens
		N_out = resp.usage.completion_tokens
		self.history[-1].update({
			'input_tokens': N_inp,
			'output_tokens': N_out,
			'end_time': time.time(),
		})
		self._last_response = resp.choices[0].message.content

	def _record_step(self, data: JSONOBJ, step: JSONOBJ):
		if len(step.choices):
			self._last_response += step.choices[0].delta.content
		if step.usage is not None:
			self.history[-1]['input_tokens'] = step.usage.prompt_tokens
			self.history[-1]['output_tokens'] = step.usage.completion_tokens
			self.history[-1]['end_time'] = time.time()

	def __repr__(self):
		return f'<{self.__class__.__name__} {self.ident}>'

	def __str__(self):
		return self.ident



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


# @fig.component('azure')
# class Azure_Client(ClientBase):
# 	@fig.silent_config_args('api_key')
# 	def __init__(self, deployment_name: str, *, api_base: str = None, api_key: str = '-', api_version: str = None,
# 				 **kwargs):
# 		super().__init__(**kwargs)
# 		self._client = openai.AzureOpenAI(api_key=api_key, api_version=api_version, azure_endpoint=api_base)
# 		self._deployment_name = deployment_name
# 		self._tokenizer = None
#
# 	def prepare(self) -> Self:
# 		self.history = []
# 		try:
# 			import tiktoken
# 		except ImportError:
# 			tokenizer = None
# 		else:
# 			tokenizer = tiktoken.get_encoding("cl100k_base")
# 		self._tokenizer = tokenizer
# 		return self
#
# 	def count_tokens(self, message: Union[str, List[Dict[str, str]]]) -> int:
# 		if isinstance(message, str):
# 			return len(self._tokenizer.encode(message))
# 		return sum(len(self._tokenizer.encode(m['content'])) for m in message)
#
# 	def stats(self) -> JSONOBJ:
# 		return {
# 			'input_tokens': sum(h['input_tokens'] for h in self.history),
# 			'output_tokens': sum(h['output_tokens'] for h in self.history),
# 			'requests': len(self.history),
# 		}
#
# 	def _record_send(self, data: JSONOBJ):
# 		self.history.append({'estimated_input_tokens': self.count_tokens(data['messages'])})
#
# 	def _record_response(self, data: JSONOBJ, resp: JSONOBJ):
# 		self.history[-1].update({
#
# 			'output_tokens': self.count_tokens(resp['response']),
# 		})
#
# 	def _record_step(self, data: JSONOBJ, step: JSONOBJ):
# 		if 'output_tokens' not in self.history[-1]:
# 			self.history[-1]['output_tokens'] = 0
# 		self.history[-1]['output_tokens'] += 1
#
# 	def wrap_chat(self, chat: List[Dict[str, str]]) -> JSONOBJ:
# 		return {'messages': chat}
#
# 	def extract_response(self, data: JSONOBJ) -> str:
# 		return data['choices'][0]['message']['content']
#
# 	def _send(self, data: JSONOBJ) -> JSONOBJ:
# 		return self._client.chat.completions.create(**data)
#
# 	def _send_no_wait(self, data: JSONOBJ) -> Iterator[JSONOBJ]:
# 		for resp in self._client.chat.completions.create(**data, stream=True):
# 			if resp['choices'][0]['finish_reason'] == 'stop':
# 				break
# 			yield resp



# @fig.component('openai')
# class OpenAI_Client(ClientBase):
# 	@fig.silent_config_args('api_key')
# 	def __init__(self, *, api_base: str = None, api_key: str = '-', api_version: str = None, **kwargs):
# 		raise NotImplementedError




