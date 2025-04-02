#%%
"""
See the readme in this directory.
"""

#region helpers
import os
import re
from openai import OpenAI
import requests

def get_hostname():
    return os.uname().nodename

def mpi_is_compute_node():
    """
    Check if it matches g<number> (compute nodes, not suited for job submissions)
    """
    hostname = get_hostname()
    return re.match(r"g\d+", hostname)
#endregion helpers


# Modify OpenAI's API key and API base to use vLLM's API server.
openai_api_key = "EMPTY"
port = os.getenv("LLM_PORT", 8001)
openai_api_base = "http://{hostname}:{port}/v1".format(hostname="localhost" if not mpi_is_compute_node() else get_hostname(), port=port)

# check if url is running
response = requests.get(f"{openai_api_base}/models")
if response.status_code == 200:
    print("vLLM API is running.")
else:
    print("vLLM API is not running.")
#%%

client = OpenAI(
    api_key=openai_api_key,
    base_url=openai_api_base,
)

models = client.models.list()
model = models.data[0].id

# Round 1
# messages = [{"role": "user", "content": "9.11 and 9.8, which is greater?"}]
text = "Implement all the rules of tic-tac-toe."
messages = [{"role": "user", "content": text}]
response = client.chat.completions.create(model=model, messages=messages, max_tokens=200)

try:
    # requires --enable-reasoning, see above
    reasoning_content = response.choices[0].message.reasoning_content
except AttributeError:
    reasoning_content = None
content = response.choices[0].message.content

print("reasoning_content:", reasoning_content)
print("content:", content)

# %%
