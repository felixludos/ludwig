from ..abstract import DECISION
from ..imports import *
from ..base import TaskBase, JudgedTask
from ..util import ToolBase, ToolError, repo_root
from .util import get_result_interpreter

import pandas as pd



@fig.component('livebench-reasoning')
class LiveBenchReasoning(JudgedTask):
	def __init__(self, subtask: str = 'zebra_puzzle', *,
				 path: Path = repo_root().joinpath('assets', 'livebench', 'livebench-reasoning.jsonl'),
				 download: bool = False, **kwargs):
		assert subtask in ['zebra_puzzle', 'spatial', 'web_of_lies_v2'], f'Invalid subtask: {subtask}'
		path = Path(path)
		super().__init__(**kwargs)
		self._data_path = path
		self._rationale_path = repo_root().joinpath('assets', 'livebench', f'rationale-{subtask}.json')
		self._auto_download = download
		self._subtask = subtask
		self._data = None
		self._rationales = None
		self._regular_inds = None

	_dev_indices = {
		'zebra_puzzle': [0, 1, 2, 3, 4, 95, 96, 97, 98, 99],
		'spatial': [22, 11, 31, 12, 38, 19, 6, 41, 27, 4],
		'web_of_lies_v2': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
	}

	def download(self, path: Path = None) -> None:
		if path is None:
			path = self._data_path
		if path.exists():
			return
		path.parent.mkdir(parents=True, exist_ok=True)

		df = pd.read_parquet("hf://datasets/livebench/reasoning/data/test-00000-of-00001.parquet")
		# take care to store dates as strings "YYYY-MM-DD" instead of integers
		df['livebench_release_date'] = pd.to_datetime(df['livebench_release_date'], unit='s').dt.strftime('%Y-%m-%d')
		df.to_json(path, lines=True, orient='records')
		print(f"Downloaded LiveBench reasoning data to {path}")

	@property
	def name(self) -> str:
		return f"LiveBench"

	def prepare(self, seed: Optional[int] = None) -> Any:
		super().prepare(seed)
		if not self._data_path.exists():
			if self._auto_download:
				self.download(self._data_path)
			else:
				raise FileNotFoundError(f"Data file not found: {self._data_path}")

		df = pd.read_json(self._data_path, lines=True)
		self._data = df[df['task'] == self._subtask].reset_index(drop=True)
		self._rationales = json.load(self._rationale_path.open('r'))
		self._regular_inds = [i for i in range(len(self._data)) if i not in self._dev_indices[self._subtask]]
		return self

	def context(self) -> str:
		return ''

	def description(self) -> str:
		return ''

	def show_keys(self) -> Iterator[str]:
		yield 'question'
		yield 'system'
		yield 'task'

	def store_keys(self) -> Iterator[str]:
		yield 'question_id'
		yield 'question'
		yield 'answer'

	@property
	def total_questions(self) -> Optional[int]:
		if self._data is None:
			return None
		return len(self._regular_inds)

	@property
	def total_dev_questions(self) -> Optional[int]:
		if self._data is None:
			return None
		return len(self._dev_indices[self._subtask])

	def json(self) -> JSONOBJ:
		return {'data_path': str(self._data_path), 'subtask': self._subtask}

	def specification(self) -> JSONOBJ:
		return {'answer': ['perfect', 'pts']}

	def ask_dev(self, index: int) -> JSONOBJ:
		assert -self.total_dev_questions-1 < index < self.total_dev_questions, f'Index out of range for dev: {index}'
		return self.ask(self._dev_indices[self._subtask][index], dev=True)

	def ask(self, index: int, *, dev: bool = False) -> JSONOBJ:
		assert self._data is not None, "Data not prepared"
		assert dev or (-self.total_questions-1 < index < self.total_questions), f'Index out of range: {index}'
		if not dev:
			index = self._regular_inds[index]

		item = self._data.iloc[index].to_dict()

		turns = item['turns']
		assert len(turns) == 1, f"Expected 1 turn, got {len(turns)}"

		item['question'] = '\n\n'.join(turns)
		item['answer'] = item['ground_truth']
		item['task'] = self.description()
		item['system'] = self.context()

		if dev and str(index) in self._rationales:
			item['rationale'] = self._rationales[str(index)]
		return item

	def interpret(self, problem: JSONOBJ, response: JSONOBJ) -> JSONOBJ:
		"""Provided code doesn't separate interpret and judge, so we do nothing here."""
		return None

	def judge(self, problem: JSONOBJ, response: JSONOBJ) -> dict[str, Union[int, float, bool]]:
		interpreter = get_result_interpreter(self._subtask, problem['livebench_release_date'])
		ground_truth, llm_answer = problem['answer'], response['final']
		score = interpreter(ground_truth, llm_answer, debug=False)
		return {'perfect': score >= 1, 'pts': score}










