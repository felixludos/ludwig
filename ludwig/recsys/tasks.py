from ..abstract import PROBLEM
from ..base import TaskBase, JudgeBase
from ..imports import *
from ..util import PromptTemplate

import numpy as np
from sklearn.metrics import roc_auc_score, ndcg_score, label_ranking_average_precision_score, precision_recall_curve, f1_score



@fig.component('venice')
class ProjectVenice(TaskBase):
	def __init__(self, clues: List[str], *, domain: str, dataroot: str, template: str = 'bounds',
				 schema: JSONOBJ = None, zero_based: bool = False, **kwargs):
		if not isinstance(template, PromptTemplate):
			template = PromptTemplate(template)
		assert domain in ['travel', 'food', 'news'], f'{domain} is not a valid domain'
		dataroot = Path(dataroot)
		if not dataroot.exists() and str(dataroot).startswith('C:'):
			dataroot = Path(f'/mnt/c{dataroot.as_posix()[2:]}'.replace('\\', '/'))
		if not dataroot.exists():
			raise FileNotFoundError(f"{dataroot} does not exist")
		super().__init__(**kwargs)
		self.clues = clues
		self.schema = json.dumps(schema, indent=2) if schema is not None else None
		self.template = template
		self.zero_based = zero_based
		self._domain_product = {'food': 'meal', 'travel': 'travel destination', 'news': 'article'}[domain]
		self.dataroot = dataroot
		self.domain = domain
		self.impressions = []

	@property
	def name(self) -> str:
		return f'{self.domain}-{self.clues if isinstance(self.clues, str) else "_".join(self.clues)}'
		return f'venice-{self.domain}'

	@property
	def total_questions(self) -> Optional[int]:
		return len(self.impressions)

	def context(self) -> str:
		return ''

	def description(self) -> str:
		# return f"Which {self._domain_product}s would the user like to see most?"
		return ''

	def specification(self) -> JSONOBJ:
		return {'answer': ['ndcg@k', 'ndcg@12', 'ndcg@6', 'map', 'auc', 'p', 'r', 'f1'],}

	def json(self) -> JSONOBJ:
		return {
			'clues': self.clues,
			'domain': self.domain,
			'zero_based': self.zero_based,
			'dataroot': str(self.dataroot),
			'template': self.template.code,
			**super().json()
		}

	def prepare(self, seed: Optional[int] = None) -> None:
		super().prepare(seed)
		import pandas as pd
		# import numpy as np

		domain = self.domain
		imps = pd.read_csv(self.dataroot.joinpath(f'{domain}-impressions.csv'))
		products = pd.read_csv(self.dataroot.joinpath(f'{domain}-products.csv'))
		products = {p['pid']: p for p in products.to_dict(orient='records')}
		users = pd.read_csv(self.dataroot.joinpath(f'{domain}-users.csv'))
		users = {u['uid']: u for u in users.to_dict(orient='records')}

		impressions = list(imps.to_dict(orient='records'))
		for imp in impressions:
			imp.update(users[imp['user']])

		self.users = users
		self.products = products
		self.impressions = impressions

	def _view_products(self, pids, numbered=False):
		products = [self.products[pid] for pid in pids]
		terms = '\n'.join([(f'{i+int(not self.zero_based)}. ' if numbered else '- ')
						   + f'**{p["title"]}**: {p["description"]}' for i, p in enumerate(products)])
		return terms

	def _user_context(self, keys: List[str], info: JSONOBJ) -> str:
		lines = []

		if keys == 'empty':
			return '[No user information currently available]'

		if 'sources' in keys or 'profile' in keys:
			if self.domain == 'news':
				terms = info['frequency']
			else:
				picks =  eval(info['companions'])
				terms = '- ' + '\n- '.join(picks)
			companions = {'travel': 'who they like to travel with',
						  'food': 'who they like to eat or cook with',
						  'news': 'how often they read the news'}[self.domain]
			lines.append(f'The user listed {companions}:\n{terms}')

			types = eval(info['source_types'])
			terms = '- ' + '\n- '.join(types)
			lines.append(f'The user listed the sources they use:\n{terms}')

		if 'desc_sources' in keys or 'habits' in keys or 'profile' in keys:
			planning = {'travel': 'plan trips', 'food': 'plan meals', 'news': 'read news'}[self.domain]
			lines.append(f'The user described how they {planning}:\n{info["desc_sources"]}')
			if self.domain == 'news':
				lines.append(f'The user described why they read the news:\n{info["reasons"]}')
		if 'desc_selection' in keys or 'habits' in keys or 'profile' in keys:
			lines.append(f"The user described the selection process for {self._domain_product}s:\n{info['desc_selection']}")

		if 'interest' in keys or 'profile' in keys:
			novelty = {'travel': 'new places', 'food': 'new meals', 'news': 'new articles'}[self.domain]
			lines.append(f"When asked how much they value personalized recommendations "
						 f"(5-point Likert scale): {info['personalized']}")
			lines.append(f"When asked how much the user values exploring {novelty} "
						 f"(5-point Likert scale): {info['explore']}")

		if 'categories' in keys:
			cats = ', '.join(eval(info['categories']))
			lines.append(f"The user selected the following categories: {cats}")

		if 'request' in keys or 'responses' in keys:
			lines.append(f"The user originally requested:\n{info['request']}")
			if 'update1' in keys or 'responses' in keys:
				lines.append(f"The user updated the request:\n{info['update1']}")
			if 'update2' in keys or 'responses' in keys:
				lines.append(f"Now, the user requested:\n{info['update2']}")
		elif 'update1' in keys or 'updates' in keys:
			lines.append(f"The user requested:\n{info['update1']}")
			if 'update2' in keys or 'updates' in keys:
				lines.append(f"Then user updated with:\n{info['update1']}")
		elif 'update2' in keys:
			lines.append(f"The user requested:\n{info['update2']}")

		if 'summary' in keys:
			lines.append(f"The user mentioned:\n{info['summary']}")

		if 'selected1' in keys or 'behavior' in keys:
			lines.append(f"The user previously selected:\n{self._view_products(eval(info['selected1']))}")
			if 'selected2' in keys or 'behavior' in keys:
				lines[-1] += '\n' + self._view_products(eval(info['selected2']))
		elif 'selected2' in keys:
			lines.append(f"The user previously selected:\n{self._view_products(eval(info['selected2']))}")

		return '\n\n'.join(lines)

	def load(self, index: int, *, seed: Optional[int] = None) -> Tuple[int, List[str]]:
		imp = self.impressions[index]
		candidates = eval(imp['candidates3'])
		selected = eval(imp['selected3'])
		return index, [candidates.index(sel) for sel in selected]

	def side_information(self, problem: int) -> JSONOBJ:
		imp = self.impressions[problem]

		return {'iid': imp['iid'], 'domain': self.domain,
				'options': eval(imp['candidates3']), 'selected': eval(imp['selected3'])}

	def observe(self, problem: int, *, seed: int = None) -> str:
		imp = self.impressions[problem]

		question = self.template.fill(
			schema=self.schema,
			json_schema=json.dumps(self.schema, indent=2),
			context=self._user_context(self.clues, imp),
			options=self._view_products(eval(imp['candidates3']), numbered=True),
			product=self._domain_product,
			products=f'{self._domain_product}s',
		)
		return question



@fig.component('1step-judge')
class VeniceJudge(JudgeBase):
	def __init__(self, format_type: str = 'json', *, pred_type: Optional[JSONABLE] = 'prob',
				 indexed: bool = False, zero_based: bool = False, beta: float = 1, set_strategy_schema: bool = True,
				 **kwargs):
		assert 0 < beta, 'Beta must be greater than 0'
		assert format_type in ['json', 'jsonblock', 'yamlblock'], f'Unknown format type: {format_type}'
		assert pred_type in ['5point', 'prob', 'binary'], f'Unknown prediction type: {pred_type}'
		super().__init__(**kwargs)
		import math
		probs = [1 / (1 + math.exp(-beta * i)) for i in range(-2, 3)]
		scales = ["Very unlikely", "Somewhat unlikely", "Neutral", "Somewhat likely", "Very likely"]
		self._scale_quant = dict(zip(scales, probs))
		self.format_type = format_type
		self.pred_type = pred_type
		self.indexed = indexed
		self.zero_based = zero_based
		self.beta = beta
		self._template = PromptTemplate(f'judges/{format_type}')
		self._set_strategy_schema = set_strategy_schema

	@property
	def name(self) -> str:
		return f'1step-{self.format_type}-{"0" if self.zero_based else ""}{"i" if self.indexed else ""}{self.pred_type}'

	def json(self) -> JSONOBJ:
		return {
			'format': self.format_type,
			'beta': self.beta,
			'pred': self.pred_type,
			'indexed': self.indexed,
			'zero_based': self.zero_based,
			**super().json()
		}

	def get_schema(self):
		typ = 'object' if self.indexed else 'array'
		title = 'User Selection Likelihoods' if self.indexed else 'User Selection Likelihoods (Ordered List)'

		indices = [str(i) for i in (range(12) if self.zero_based else range(1,13))]

		value_title = 'Selection' if self.pred_type == 'binary' else 'Likelihood Value'
		value_desc = {
			'5point': 'The likelihood from a 5-point Likert scale.',
			'prob': 'The probability the user will select the corresponding suggestion above.',
			'binary': 'Whether the user will select the corresponding suggestion above.',
		}[self.pred_type]

		schemas = {
			('5point', True): {
				"title": title,
				"description": f"A dictionary of exactly 12 items. Keys are strings from \"{0 if self.zero_based else 1}\" to \"{11 if self.zero_based else 12}\", and each value is a string representing the likelihood a user will select a corresponding suggestion, based on a 5-point Likert scale.",
				"type": typ,
				"properties": {
					**{i: {
						"title": f"{value_title} {i}",
						"description": value_desc,
						"type": "string",
						"enum": [
							"Very unlikely",
							"Somewhat unlikely",
							"Neutral",
							"Somewhat likely",
							"Very likely"
						]
					} for i in indices}
				},
				"required": indices,
				"additionalProperties": False,
			},
			('5point', False): {
				"title": title,
				"description": "A list of exactly 12 strings, each representing the likelihood a user will select the corresponding suggestion above.",
				"type": typ,
				"minItems": 12,
				"maxItems": 12,
				"items": {
					"title": value_title,
					"description": value_desc,
					"type": "string",
					"enum": [
						"Very unlikely",
						"Somewhat unlikely",
						"Neutral",
						"Somewhat likely",
						"Very likely"
					]
				}
			},
			('prob', True): {
				"title": title,
				"description": f"A dictionary of exactly 12 items. Keys are strings from \"{0 if self.zero_based else 1}\" to \"{11 if self.zero_based else 12}\", and each value is a float representing the likelihood a user will select a corresponding suggestion, based on a 5-point Likert scale.",
				"type": typ,
				"properties": {
					**{i: {
						"title": f"{value_title} {i}",
						"description": value_desc,
						"type": "number",
						"minimum": 0,
						"maximum": 1
					} for i in indices}
				},
				"required": indices,
				"additionalProperties": False,
			},
			('prob', False): {
				"title": title,
				"description": "A list of exactly 12 floats, each representing the likelihood a user will select the corresponding suggestion above.",
				"type": typ,
				"minItems": 12,
				"maxItems": 12,
				"items": {
					"title": value_title,
					"description": value_desc,
					"type": "number",
					"minimum": 0,
					"maximum": 1
				}
			},
			('binary', True): {
				"title": title,
				"description": f"A dictionary of exactly 12 items. Keys are strings from \"{0 if self.zero_based else 1}\" to \"{11 if self.zero_based else 12}\", and each value is a string (\"yes\" or \"no\") representing whether the user will select the corresponding suggestion above.",
				"type": typ,
				"properties": {
					**{i: {
						"title": f"{value_title} {i}",
						"description": value_desc,
						"type": "string",
						"enum": [
							"Yes",
							"No"
						]
					} for i in indices}
				},
				"required": indices,
				"additionalProperties": False,
			},
			('binary', False): {
				"title": title,
				"description": "A list of exactly 12 strings (\"yes\" or \"no\"), representing whether the user will select the corresponding suggestion above.",
				"type": typ,
				"minItems": 12,
				"maxItems": 12,
				"items": {
					"title": value_title,
					"description": value_desc,
					"type": "string",
					"enum": [
						"Yes",
						"No"
					]
				}
			}
		}

		if (self.pred_type, self.indexed) not in schemas:
			raise NotImplementedError(f'Unknown prediction type: {self.pred_type} and indexed: {self.indexed}')

		schema = schemas[self.pred_type, self.indexed]
		return schema

	def prepare(self, task_spec: JSONOBJ) -> None:
		super().prepare(task_spec)

		if self._set_strategy_schema:
			strategy = self._my_config.pull('strategy', silent=True)
			strategy.params['grammar'] = self.get_schema()

		answers = task_spec['answer']
		assert isinstance(answers, list), f'Answers must be a list, got {type(answers)}: {answers}'

	def format_description(self, task_description: str) -> str:
		schema = self.get_schema()
		desc = self._template.fill(
			task_context = task_description,
			schema = self.get_schema(),
			json_schema=json.dumps(schema, indent=2) if schema is not None else None,
		)
		return desc

	def interpret(self, question: str, response: str) -> Tuple[List[str], None]:
		if self.format_type == 'json':
			try:
				decision = json.loads(response)
			except json.JSONDecodeError:
				print(f'Failed to parse JSON: {response}')
				return None, None

		elif self.format_type == 'jsonblock':
			json_match = re.search(r'```json(.*?)```', response, re.DOTALL)
			try:
				json_str = json_match.group(1)
				decision = json.loads(json_str)
			except:
				# raise
				return None, None

		elif self.format_type == 'yamlblock':
			import yaml
			yaml_match = re.search(r'```yaml(.*?)```', response, re.DOTALL)
			try:
				yaml_str = yaml_match.group(1)
				decision = yaml.safe_load(yaml_str)
			except:
				# raise
				return None, None

		else:
			raise NotImplementedError(f'Unknown format type: {self.format_type}')

		if self.indexed:
			inds = {int(k): v for k, v in decision.items()}
			order = sorted(inds.keys())
			decision = [inds[i] for i in order]
		elif isinstance(decision, dict): # some grammars require top-level to be an object
			assert len(decision) == 1
			decision = next(iter(decision.values()))

		if len(decision) != 12:
			return None, None

		return decision, None


	def judge(self, decision: Union[List[str], List[float]],
			  answer: List[int], info: Optional[JSONOBJ] = None) -> Optional[Dict[str, float]]:

		if decision is None:
			self._failures += 1
			return None

		if self.pred_type == '5point':
			probs = np.array([self._scale_quant[dec] for dec in decision]).reshape(1, -1)
		elif self.pred_type == 'prob':
			probs = np.array([float(dec) for dec in decision]).reshape(1, -1)
		elif self.pred_type == 'binary':
			probs = np.array([1 if dec.lower() == 'yes' else 0 for dec in decision]).reshape(1, -1)
		else:
			raise NotImplementedError(f'Unknown prediction type: {self.pred_type}')

		ground_truth = np.array([i in answer for i in range(len(decision))]).reshape(1, -1)

		scores = {}

		scores['map'] = label_ranking_average_precision_score(ground_truth, probs).item()
		scores['auc'] = roc_auc_score(ground_truth.astype(int).reshape(-1), probs.reshape(-1)).item()
		scores['ndcg@k'] = ndcg_score(ground_truth, probs, k=len(answer)).item()
		scores['ndcg@12'] = ndcg_score(ground_truth, probs, k=12).item()
		scores['ndcg@6'] = ndcg_score(ground_truth, probs, k=6).item()

		self._successes += 1
		return scores


from ..evaluation.judging import ClientJudge, ClientStats, AbstractClient

@fig.component('2step-judge')
class Venice2stepJudge(VeniceJudge):
	def __init__(self, client: AbstractClient, **kwargs):
		super().__init__(set_strategy_schema=False, **kwargs)
		self._client = client

	def format_description(self, task_description: str) -> str:
		return task_description

	@property
	def name(self) -> str:
		return f'2step-{self.format_type}-{"0" if self.zero_based else ""}{"i" if self.indexed else ""}{self.pred_type}'

	def prepare(self, task_spec: JSONOBJ) -> None:
		super().prepare(task_spec)
		if not self._client.ping():
			raise ValueError(f'Judge client {self._client.ident} is not ready to use.')
		self._client.prepare()

	def json(self) -> JSONOBJ:
		return {'client': self._client.json(), **super().json()}

	def collect_stats(self, include_start: bool = False, **kwargs) -> ClientStats:
		return ClientStats(self._client, include_start=include_start, **kwargs)

	def status(self) -> JSONOBJ:
		return {
			'client': self._client.stats(),
			**super().status(),
		}

	def interpret(self, question: str, response: str) -> Tuple[JSONABLE, Optional[JSONOBJ]]:

		schema = self.get_schema()

		prompt = self._template.fill(
			schema = schema,
			json_schema=json.dumps(schema, indent=2) if schema is not None else None,
		)
		chat = [
			{'role': 'user', 'content': question},
			{'role': 'assistant', 'content': response},
			{'role': 'user', 'content': prompt},
		]

		resp = self._client.send(self._client.wrap_chat(chat,
						grammar=None if self.format_type.endswith('block') else schema))

		formatted_response = self._client.extract_response(resp)

		decicion, info = super().interpret(question, formatted_response)

		return decicion, info

