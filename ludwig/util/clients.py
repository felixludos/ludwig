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
		return {'response': f'This is the mock response to a chat with {len(chat)} messages.'}

	def _send_no_wait(self, data):
		resp = self._send(data)
		for token in resp['response'].split():
			time.sleep(0.03)
			yield {'response': token}



class OpenaiClientBase(ClientBase):
	def __init__(self, endpoint: Union[openai.OpenAI, str], *, max_tokens: int = None, seed: int = None,
				 temperature: float = None, top_p: float = None, **kwargs):
		if isinstance(endpoint, str):
			endpoint = openai.OpenAI(api_key='EMPTY', base_url=endpoint)
		super().__init__(**kwargs)
		self.endpoint = endpoint

		self.max_tokens = max_tokens
		self.temperature = temperature
		self.top_p = top_p
		self.seed = seed

		self._tokenizer = None
		self.history = None
		self._model_name = None
		self._last_response = None

	@property
	def ident(self) -> str:
		if self._model_name is None:
			return f'{self.endpoint.base_url}'
		return f'{self._model_name}'

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

	def json(self) -> JSONOBJ:
		return {
			'base_url': str(self.endpoint.base_url),
			'model_name': self._model_name,
			'max_tokens': self.max_tokens,
			'temperature': self.temperature,
			'top_p': self.top_p,
			'seed': self.seed,
			**super().json()
		}

	def past_requests(self) -> int:
		return len(self.history)

	def stats(self, starting_from: int = 0) -> JSONOBJ:
		def _metrics(seq: Sequence[float]):
			return {'mean': sum(seq) / len(seq), 'min': min(seq), 'max': max(seq),}
		data = {}
		times = [h['end_time'] - h['start_time'] for h in self.history[starting_from:] if 'end_time' in h]
		if times:
			tps = [h['output_tokens']/(h['end_time'] - h['start_time'])
				   for h in self.history[starting_from:] if 'end_time' in h]
			data['time'] = _metrics(times)
			data['tok_per_sec'] = _metrics(tps)
		return {
			'input_tokens': sum(h['input_tokens'] for h in self.history[starting_from:]),
			'output_tokens': sum(h['output_tokens'] for h in self.history[starting_from:]),
			**data,
			'requests': len(self.history[starting_from:]),
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
		return self.endpoint.chat.completions.create(**data)

	def _send_no_wait(self, data):
		for chunk in self.endpoint.chat.completions.create(
				**data, stream=True, stream_options={"include_usage": True}):
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
		self.history.append({})
		if self._tokenizer is not None:
			self.history[-1]['estimated_input_tokens'] = self.count_tokens(data['messages'])
		self.history[-1]['start_time'] = time.time()

	def _record_response(self, data: JSONOBJ, resp: openai.ChatCompletion):
		N_inp = resp.usage.prompt_tokens
		N_out = resp.usage.completion_tokens
		self.history[-1].update({
			'input_tokens': N_inp,
			'output_tokens': N_out,
			'end_time': time.time(),
		})
		self._last_response = resp.choices[0].message.content

	def _record_step(self, data: JSONOBJ, step: openai.ChatCompletion):
		if len(step.choices):
			self._last_response += step.choices[0].delta.content
		if step.usage is not None:
			self.history[-1]['input_tokens'] = step.usage.prompt_tokens
			self.history[-1]['output_tokens'] = step.usage.completion_tokens
			self.history[-1]['end_time'] = time.time()

	def ping(self) -> bool:
		return True # TODO: implement a ping method for OpenAI endpoints

	def __str__(self):
		return self.ident



@fig.component('vllm')
class vllm_Client(OpenaiClientBase):
	def __init__(self, addr: Union[str, int], **kwargs):
		super().__init__(endpoint=self._to_full_addr(addr), **kwargs)

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

	def prepare(self) -> Self:
		super().prepare()
		info = self._server_model_info()
		self._model_name = info['data'][0]['id']
		return self

	def ping(self) -> bool:
		try:
			url = self.endpoint.base_url
			response = requests.get(f"{str(url).replace(url.path, '')}/ping")
			response.raise_for_status()
			return response.status_code == 200
		except requests.RequestException as e:
			print(f"Error pinging server: {e}")
			return False



@fig.component('azure')
class OpenaiAzure_Client(OpenaiClientBase):
	@fig.silent_config_args('api_key')
	def __init__(self, model_name: str, *, api_base: str, api_key: str, api_version: str, **kwargs):
		endpoint = openai.AzureOpenAI(azure_endpoint=api_base, api_key=api_key, api_version=api_version)
		super().__init__(endpoint=endpoint, **kwargs)
		self._model_name = model_name



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



