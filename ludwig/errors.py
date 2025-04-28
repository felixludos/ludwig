from .imports import *

class OptionalMethodNotImplemented(NotImplementedError):
	"""Raised by method stubs (usually in abstract classes) that are not implemented, but are not required."""
	pass


class ParsingError(ValueError):
	"""Raised when the LLM's response cannot be parsed into a valid answer."""
	def __init__(self, response: str, message: str):
		super().__init__(f'{message}: {response!r}')
		self.response = response
		self.message = message


class AmbiguousFormalizationError(Exception):
	"""Raised when the LLM's response cannot be parsed into a valid call to a tool."""
	pass


class ToolError(Exception):
	"""Raised when a tool fails to execute or returns an error."""
	pass


class ExceededBudgetError(Exception):
	"""Raised when the maximum budget is exceeded."""
	def __init__(self, message: str):
		super().__init__(message)
		self.message = message


class ExceededRetriesError(ExceededBudgetError):
	"""Raised when the maximum number of retries is exceeded."""
	def __init__(self, message: str):
		super().__init__(message)
		self.message = message
