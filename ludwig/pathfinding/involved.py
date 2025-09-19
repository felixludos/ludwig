from ..imports import *

from .util import PathTask, to_graph, all_paths, select_paths



@fig.component('path/direct-route')
class DirectRoute(PathTask):
	def __init__(self, graph: int = 1, **kwargs):
		super().__init__(**kwargs)
		self._graph_index = graph
		self._graph = None
		self._path_questions = None

	def get_current_graph(self):
		return self._graph

	@property
	def name(self) -> str:
		return f"DirectRoute{self._graph_index}"

	def show_keys(self) -> Iterator[str]:
		yield 'question'
		yield 'system'
		yield 'task'

	def store_keys(self) -> Iterator[str]:
		yield 'problem'
		yield 'question'
		yield 'answer'

	def json(self) -> JSONOBJ:
		return {
			'graph_index': self._graph_index,
			'data_path': str(self._data_path),
		}

	@property
	def total_questions(self) -> Optional[int]:
		if self._path_questions is None:
			return None
		return len(self._path_questions)

	@property
	def total_dev_questions(self) -> Optional[int]:
		if self._data is None:
			return None
		return len(self._data) - 1

	def prepare(self, seed: Optional[int] = None) -> 'Self':
		super().prepare(seed)

		self._item = self._data[self._graph_index]
		G = to_graph(self._item)
		self._graph = G

		questions = []
		for a, b, used, unused in select_paths(G):
			for target in used:
				questions.append({'start': a, 'end': b, 'target': target, 'answer': 'yes'})
			for target in unused:
				questions.append({'start': a, 'end': b, 'target': target, 'answer': 'no'})

		rng = random.Random(5099)
		rng.shuffle(questions)
		self._path_questions = questions
		return self

	def specification(self) -> JSONOBJ:
		return {'answer': 'yes/no'}

	def description(self) -> str:
		return ("You will be provided with a short fiction text and a graph "
				"representing locations and their connections. Your task is to determine "
				"whether there exists a route without backtracking from a specified start "
				"location to an end location that involves passing through a specified target location.")

	def context(self) -> str:
		return ("You are an expert in pathfinding and mapping tasks. Specifically, when given a detailed description "
				"of locations and their connections, you can analyze the information to determine possible routes "
				"between locations. You are skilled at identifying paths that meet specific criteria, such as avoiding "
				"backtracking and including certain waypoints.")

	def ask(self, index: int) -> JSONOBJ:
		ctx = {}

		info = self._path_questions[index]
		start, end, target = info['start'], info['end'], info['target']
		answer = info['answer']
		ctx['problem'] = [start, end, target]
		ctx['answer'] = answer

		ctx['edges'] = self._item['task1']['target']
		ctx['text'] = self._item['text']

		text = self._item['text']
		# question = (f"{text}\n\n---\n\n"
		# 			f"Based on the text, does a route without backtracking "
		# 			f"starting from **{start}** to **{end}** exist which involves **{target}**?")

		question = f"""{text}

Now, consider the path details:
- starting location: **{start}**
- end location: **{end}**
- target location: **{target}**

Based on the text, does a route without backtracking exist from the starting to the end location which involves the target location?"""
		ctx['question'] = question

		ctx['rationale'] = list(self._rationale(ctx))

		ctx['system'] = self.context()
		ctx['task'] = self.description()
		return ctx

	def ask_dev(self, index: int) -> JSONOBJ:
		dev_index = (self._graph_index + 1 + index) % len(self._data)
		if dev_index == self._graph_index:
			raise ValueError(f"Dev index collision: {dev_index}")
		return self.__class__(graph=dev_index, data_path=self._data_path).prepare().ask(0)

	def _rationale(self, ctx: JSONOBJ) -> Iterator[str]:
		start, end, target = ctx['problem']

		# Step 1: Define the objective and strategy
		yield (f"**Objective:** The goal is to find a route from **{start}** to **{end}** that passes through "
			   f"**{target}** without visiting any location more than once (i.e., no backtracking).")

		yield (f"**Strategy:** Break the problem into two parts: "
			   f"first, find the direct paths from **{start}** to **{end}** (without backtracking). "
			   f"Then, check if any of these paths include **{target}**.")

		paths = all_paths(self._graph, start, end)
		assert len(paths)
		path_info = '\n- '.join([' -> '.join(p) for p in paths])

		yield (f"**Find Direct Paths:** First, let's identify all direct paths from **{start}** to **{end}**. "
			   f"Here are the paths found:\n- {path_info}")

		if ctx['answer'] == 'yes':
			output = f'At least one of these paths includes **{target}**.'
		else:
			output = f'It appears that none of these paths include **{target}**.'

		yield (f"**Check for Target Inclusion:** Next, we need to check if any of these paths "
			   f"include the target location **{target}**. {output}")

		answer = ctx['answer']

		yield f"**Conclusion:** Therefore, the answer to the question is **{answer.capitalize()}**."





