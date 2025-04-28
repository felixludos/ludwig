from .imports import *
from .files import repo_root
from .clients import vllm_Client
from .search import GenericSearch
from .parsers import PythonParser


def test_repo_root():
	root = repo_root()

	assert root.joinpath('assets').exists()
	assert root.joinpath('ludwig').exists()
	assert root.joinpath('main.py').exists()



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



