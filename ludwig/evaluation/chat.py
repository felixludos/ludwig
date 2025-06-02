from .imports import *

from ..util import PromptTemplate, AbstractClient


@fig.component('chat-interface')
class ChatInterface(fig.Configurable):
	def __init__(self, client: AbstractClient, system_message: Union[PromptTemplate, str] = None, 
			     *, host: str = None, port: int = 7860, examples: list[str] = None, **kwargs):
		if system_message is not None and not isinstance(system_message, PromptTemplate):
			system_message = PromptTemplate(system_message)
		super().__init__(**kwargs)
		self.client = client
		self.system_message = system_message
		self.host = host
		self.port = port
		self._examples = examples

	def prepare(self):
		self.client.prepare()

	def run(self) -> JSONOBJ:
		import gradio as gr
		self.interface = gr.ChatInterface(
			self.step,
			# chatbot=gr.Chatbot(height=690),
			textbox=gr.Textbox(placeholder="Chat with me!", container=False, scale=7),
			# description=f"Spec: {self.info['model_device_type']} {self.info['model_dtype']}  "
			# 			f"|  version: {self.info['version']}",
			title=f"Chat with {self.client.model_name}",
			examples=self._examples,
			# retry_btn="Retry",
			# undo_btn="Undo",
			# clear_btn="Clear",
		)
		self.interface.queue().launch(server_name=self.host, server_port=self.port)

	def step(self, message: str, history: list[tuple[str, str]]):
		chat = []
		if self.system_message is not None:
			chat.append({'role': 'system', 'content': self.system_message})
		for user, assistant in history:
			chat.append({'role': 'user', 'content': user})
			chat.append({'role': 'assistant', 'content': assistant})
		chat.append({'role': 'user', 'content': message})

		response = ''
		for token in self.client.stream_response(chat):
			response += token
			yield response



@fig.script('chat', description='Launch a chat interface')
def launch_chat(cfg: fig.Configuration):
	"""
	Launch a chat interface for the given configuration.
	"""

	client = cfg.pull('client', None, silent=True)
	if client is None:
		cfg.push('client._type', 'vllm', silent=True, overwrite=False)

	cfg.push('interface._type', 'chat-interface', silent=True, overwrite=False)
	interface = cfg.pull('interface')

	interface.prepare()

	return interface.run()













