from ..abstract import PROBLEM
from ..base import TaskBase, JudgeBase
from ..imports import *
from ..util import PromptTemplate


@fig.component('venice')
class ProjectVenice(TaskBase):
	def __init__(self, clues: List[str], *, domain: str, dataroot: str, template: str = 'recs5',
				 schema: JSONOBJ = None, **kwargs):
		if not isinstance(template, PromptTemplate):
			template = PromptTemplate(template)
		assert domain in ['travel', 'food', 'news'], f'{domain} is not a valid domain'
		dataroot = Path(dataroot)
		if not dataroot.exists():
			raise FileNotFoundError(f"{dataroot} does not exist")
		super().__init__(**kwargs)
		self.clues = clues
		self.schema = json.dumps(schema, indent=2) if schema is not None else None
		self.template = template
		self._domain_product = {'food': 'meal', 'travel': 'travel destination', 'news': 'article'}[domain]
		self.dataroot = dataroot
		self.domain = domain
		self.impressions = []

	@property
	def name(self) -> str:
		return f'venice-{self.domain}'

	@property
	def total_questions(self) -> Optional[int]:
		return len(self.impressions)

	def context(self) -> str:
		return ''

	def description(self) -> str:
		return f"Which {self._domain_product}s would the user like to see most?"

	def specification(self) -> JSONOBJ:
		return {'answer': 'yes/no'}

	def json(self) -> JSONOBJ:
		return {
			'clues': self.clues,
			'domain': self.domain,
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
		for imp in self.impressions:
			imp.update(users[imp['user']])

		self.users = users
		self.products = products
		self.impressions = impressions

	def _view_products(self, pids, numbered=False):
		products = [self.products[pid] for pid in pids]
		terms = '\n'.join([(f'{i+1}. ' if numbered else '- ')
						   + f'**{p["title"]}**: {p["description"]}' for i, p in enumerate(products)])
		return terms

	def _user_context(self, keys: List[str], info: JSONOBJ) -> str:
		lines = []

		if 'profile' in keys:
			picks = eval(info['frequency' if self.domain == 'news' else 'companions'])
			terms = '- ' + '\n- '.join(picks)
			companions = {'travel': 'who they like to travel with',
						  'food': 'who they like to eat or cook with',
						  'news': 'how often they read the news'}[self.domain]
			lines.append(f'The user listed {companions}:\n{terms}')

			types = eval(info['source_types'])
			terms = '- ' + '\n- '.join(types)
			lines.append(f'The user listed the sources they use:\n{terms}')

		if 'desc_sources' in keys or 'desc' in keys:
			planning = {'travel': 'plan trips', 'food': 'plan meals', 'news': 'read news'}[self.domain]
			lines.append(f'The user described how they {planning}:\n{info["desc_sources"]}')
			if self.domain == 'news':
				lines.append(f'The user described why they read the news:\n{info["reasons"]}')
		if 'desc_selection' in keys or 'desc' in keys:
			lines.append(f"The user described the selection process for {self._domain_product}s:\n{info['desc_selection']}")

		if 'interest' in keys:
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
			context=self._user_context(self.clues, imp),
			options=self._view_products(eval(imp['candidates3']), numbered=True),
			product=self._domain_product,
			products=f'{self._domain_product}s',
		)
		return question



@fig.component('json-judge')
class JsonJudge(JudgeBase):
	@property
	def name(self) -> str:
		return 'json-judge'

	def interpret(self, question: str, response: str) -> Tuple[List[str], Optional[JSONOBJ]]:

		decision = json.loads(response)

		return decision, None








