from .imports import *


class AbstractClient:
	@property
	def ident(self) -> str:
		raise NotImplementedError

	def ping(self) -> bool:
		raise NotImplementedError

	def prepare(self) -> 'Self':
		raise NotImplementedError

	def json(self) -> JSONOBJ:
		raise NotImplementedError

	def stats(self, starting_from: int = 0) -> JSONOBJ:
		raise NotImplementedError

	def past_requests(self) -> int:
		raise NotImplementedError

	def wrap_prompt(self, prompt: str, params: JSONOBJ = {}) -> JSONOBJ:
		raise NotImplementedError

	def begin_chat(self, prompt: Optional[str] = None, *, role: str = 'user') -> List[Dict[str, str]]:
		raise NotImplementedError

	def wrap_chat(self, chat: List[Dict[str, str]], params: JSONOBJ = {}) -> JSONOBJ:
		raise NotImplementedError

	def send_no_wait(self, data: JSONOBJ) -> JSONOBJ:
		raise NotImplementedError

	def send(self, data: JSONOBJ) -> JSONOBJ:
		raise NotImplementedError

	def multi_turn(self, chat: List[Dict[str, str]], params: JSONOBJ = {},
				   *, max_retries: int = None) -> Iterator[JSONOBJ]:
		raise NotImplementedError

	def get_response(self, prompt: Union[str, List[Dict[str, str]]], **params) -> str:
		raise NotImplementedError

	def step(self, chat: Union[str, List[Dict[str, str]]], *, auto_resolve_tools: bool = True, **params) -> JSONOBJ:
		raise NotImplementedError

	def last_response(self) -> Optional[str]:
		raise NotImplementedError

	def stream_response(self, prompt: Union[str, List[Dict[str, str]]], **params) -> Iterator[str]:
		raise NotImplementedError

	def extract_response(self, data: JSONOBJ) -> str:
		raise NotImplementedError

	def count_tokens(self, message: str) -> int:
		raise NotImplementedError



