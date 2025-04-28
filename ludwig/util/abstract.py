from .imports import *



class AbstractClient:
	@property
	def ident(self) -> str:
		raise NotImplementedError

	def ping(self) -> bool:
		raise NotImplementedError

	def prepare(self) -> Self:
		raise NotImplementedError

	def json(self) -> JSONOBJ:
		raise NotImplementedError

	def stats(self, starting_from: int = 0) -> JSONOBJ:
		raise NotImplementedError

	def past_requests(self) -> int:
		raise NotImplementedError

	def wrap_prompt(self, prompt: str) -> JSONOBJ:
		raise NotImplementedError

	def wrap_chat(self, chat: List[Dict[str, str]]) -> JSONOBJ:
		raise NotImplementedError

	def send_no_wait(self, data: JSONOBJ) -> JSONOBJ:
		raise NotImplementedError

	def send(self, data: JSONOBJ) -> JSONOBJ:
		raise NotImplementedError

	def multi_turn(self, chat: Union[str, List[Dict[str, str]]], *, max_retries: int = None,
				   user_role: str = 'user', assistant_role: str = 'assistant',
				   **params) -> Iterator[List[Dict[str, str]]]:
		raise NotImplementedError

	def get_response(self, prompt: Union[str, List[Dict[str, str]]], **params) -> str:
		raise NotImplementedError

	def last_response(self) -> Optional[str]:
		raise NotImplementedError

	def stream_response(self, prompt: Union[str, List[Dict[str, str]]], **params) -> Iterator[str]:
		raise NotImplementedError

	def extract_response(self, data: JSONOBJ) -> str:
		raise NotImplementedError

	def count_tokens(self, message: str) -> int:
		raise NotImplementedError



