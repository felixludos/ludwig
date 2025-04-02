# ludwig

## Getting Started
```bash

# git clone TODO ~/autoformalization/code/ludwig/
cd ~/venvs/
python3.10 -m venv ludwig_venv
source ~/venvs/ludwig_venv/bin/activate
pip install --upgrade pip
cd ~/autoformalization/code/ludwig/
# pip install -r requirements.txt # may take some time, inspect .venv/lib/python3.10/site-packages/ to see progress
# pip uninstall -y ludwig
pip install -e ./
pip install pre-commit
pre-commit install # optional
# test
python -c 'import torch; print("Cuda:", torch.cuda.is_available()); import transformers'

# pip uninstall -y hf_helpers; pip install -e /home/mmordig/formalization_proj/hf_helpers
```

Select interpreter: `~/venvs/ludwig_venv/bin/python3.10`
