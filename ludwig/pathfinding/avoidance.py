import random

from ..abstract import PROBLEM
from ..imports import *
from ..base import TaskBase
from ..util import ToolBase, ToolError, repo_root



@fig.component('ttt/take-the-middle')
class CanIAvoid(TaskBase):
	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self._data_path = repo_root().joinpath('assets', 'plugh', 'plugh.json')

	@property
	def name(self) -> str:
		return f"Avoid"

	def prepare(self, seed: Optional[int] = None) -> Any:
		super().prepare(seed)
		if not self._data_path.exists():
			raise FileNotFoundError(f"Data file not found: {self._data_path}")
		self._data = json.load(self._data_path.open('r'))

	def show_keys(self) -> Iterator[str]:
		yield 'question'
		yield 'system'
		yield 'task'

	def store_keys(self) -> Iterator[str]:
		yield 'problem'
		yield 'question'
		yield 'answer'







