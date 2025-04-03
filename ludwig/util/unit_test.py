from .imports import *
from .files import repo_root
from .clients import vllm_Client


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


