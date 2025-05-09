import random

from .imports import *
from .files import repo_root
from .clients import vllm_Client, OpenaiAzure_Client, Tool_Client
from .search import GenericSearch
from .parsers import PythonParser
from .tools import ToolBase, ToolError


def test_repo_root():
	root = repo_root()

	assert root.joinpath('assets').exists()
	assert root.joinpath('ludwig').exists()
	assert root.joinpath('main.py').exists()



def test_tool():
	random.seed(1000000009)

	class GetWeather(ToolBase):
		@property
		def name(self) -> str:
			return 'get_current_weather'

		def description(self) -> str:
			return "Get the current weather in a given location"

		def schema(self, style: str = None) -> JSONOBJ:
			return {
				"type": "function",
				"function": {
					"name": self.name,
					"description": self.description(),
					"parameters": {
						"type": "object",
						"properties": {
							"city": {
								"type":
									"string",
								"description":
									"The city to find the weather for, e.g. 'San Francisco'"
							},
							"country": {
								"type":
									"string",
								"description":
									"the country (may be a 3 letter code) that the city is"
									" in, e.g. 'AUT' which would mean 'Austria'"
							},
							"unit": {
								"type": "string",
								"description": "The unit to fetch the temperature in",
								"enum": ["celsius", "fahrenheit"],
								"default": "celsius"
							}
						},
						"required": ["city", "country"]
					}
				}
			}

		def call(self, arguments: JSONOBJ, *, seed: Optional[int] = None) -> str:
			"""
			Calls the tool with the given arguments and returns the result as a string.

			:param arguments: should adhere to the expected input specification. If not, will raise a `ToolError`.
			:param seed: optional to ensure deterministic behavior
			:raises: ToolError
			"""
			assert isinstance(arguments, dict), f'Expected a dict, got {type(arguments)}'
			if 'city' not in arguments:
				raise ToolError("Missing 'city' in arguments")
			if 'country' not in arguments:
				raise ToolError("Missing 'country' in arguments")

			rng = random.Random(seed)

			temp = rng.randint(15, 35)

			city = arguments.get('city')
			fixed = {'Dallas': 31, 'Jakarta': 25, 'Barcelona': 28}
			if city in fixed:
				temp = fixed[city]

			country = arguments.get('country')

			unit = arguments.get('unit', 'celsius')
			if unit == 'fahrenheit':
				temp = temp * 9 / 5 + 32

			weather = rng.choice(['sunny', 'cloudy', 'rainy', 'dry'])
			# return f"The weather in {city}, {country} is {temp} degrees {unit} and {weather}."
			return json.dumps({'city': city, 'country': country, 'unit': unit, 'temp': temp, 'weather': weather})

	class Client(Tool_Client, vllm_Client):
		pass

	client = Client(addr='8000', tools=[GetWeather()])
	client.prepare()

	data = client.json()
	print(data)

	if not client.ping():
		raise RuntimeError("Client is not reachable.")
	print()

	chat = [{'role': 'user', 'content': "What is the weather in Dallas?"}]
	r = client.step(chat, max_tokens=512)
	print(chat[-1]['content'])
	assert chat[-1]['role'] == 'assistant'

	chat = [{'role': 'user', 'content': "Is it warmer in Dallas or Barcelona today?"}]
	r = client.step(chat, max_tokens=512)
	print(chat[-1]['content']) # answer should be Dallas
	assert chat[-1]['role'] == 'assistant'

	stats = client.stats()
	print(stats)

	chat = [{'role': 'user', 'content': "Is it warmer in Barcelona or Jakarta right now? "
										"Answer only with either 'Barcelona' or 'Jakarta'."}]
	r = client.step(chat, max_tokens=512)
	print(chat[-1]['content']) # answer should be Barcelona
	assert chat[-1]['role'] == 'assistant'

	statsend = client.stats()
	print(statsend)


def test_azure_client():
	raise Exception('skipped')

	path = repo_root().joinpath('config', 'secrets', 'azure.yml')

	import yaml
	with path.open('r') as f:
		azure_config = yaml.safe_load(f)

	client = OpenaiAzure_Client(model_name=azure_config['model-name'], api_base=azure_config['api-base'],
								api_key=azure_config['api-key'], api_version=azure_config['api-version'])
	client.prepare()

	response = client.get_response("hi", max_tokens=1, temperature=0.)
	assert response == 'Hello'
	print(response)

	stats = client.stats()
	print(stats)


def test_vllm_client():

	client = vllm_Client(addr='8000')

	if not client.ping():
		print("Client is not reachable.")
		return

	client.prepare()

	print(client.ident)

	resp = client.get_response("Is today Tuesday? Answer in one word.", max_tokens=10)
	print(resp)

	assert resp == client.last_response()

	msg = ''
	for tok in client.stream_response("Tell me a short joke.", max_tokens=20):
		msg += tok
		print(tok, end='', flush=True)
	print()

	assert msg == client.last_response()

	stats = client.stats()

	print(stats)

	info = client.json()

	print(info)

_long_prompt = '''**Instructions:** You are a masterful fantasy storyteller. Write a first-person short story (1,000–1,500 words) from the perspective of a cunning rogue on a quest to retrieve a lost artifact guarded by a fearsome dragon. Start in a bustling trade city bordering a vast desert, then detail the journey through a perilous wilderness. Include:
 
1. **Three key side characters**: a scheming rival, a loyal ally, and a mysterious guide.  
2. Vivid descriptions of **at least one major landscape feature** along the way.  
3. A tense final confrontation in the dragon’s lair.  
4. The rogue’s **internal monologue** revealing doubts, motivations, and clever tactics.  
5. A conclusion that shows how the quest changes or challenges the rogue.

Use descriptive language to immerse the reader, maintain a consistent narrative voice, and ensure the story remains suspenseful yet cohesive. Incorporate local legends, cultural tidbits, or subtle magical details to enhance the world-building. End with a resolution—triumphant or bittersweet—that reflects the rogue’s growth.'''
def test_long_generation():

	client = vllm_Client(addr='8000')

	if not client.ping():
		print("Client is not reachable.")
		return

	client.prepare()

	print(client.ident)

	resp = client.get_response(_long_prompt)
	print()
	print(resp)

	stats = client.stats()

	print(stats)

	info = client.json()

	print(info)


def test_search():
	random.seed(1000000009)
	words = {"cat", "cot", "cog", "dog", "dot"}
	target = 'dog'

	def expand(path):
		"""Expand a word by changing one letter."""
		result = []
		word = path[-1]
		history = set(path)
		for w in words:
			if w not in history and sum(a != b for a, b in zip(word, w)) == 1:
				result.append(w)
		return result

	def extract(path):
		if path[-1] == target:
			return path


	search = GenericSearch(fuel=100, check_first=2)
	search.set_expand_fn(expand)
	search.set_extract_fn(extract)

	result = search.run("cat")
	assert result == [3,3]


def test_parser():

	parser = PythonParser()
	parser.prepare()

	code = '''```python
def f(x):
	return g(x) + 1
def g(y):
	return 2*y
f(10)
```'''

	blocks = parser.parse(code)

	assert blocks[0]['unsafe'] is None

	item = parser.realize(blocks[0])

	assert 'error' not in item
	assert 'f' in item['local_vars']
	assert item.get('result') == 21

	assert item['local_vars']['f'](10) == 21

	print()
	print(item)





