#!/usr/bin/env bash

: '
Basic launcher with no GPUs, loading the environment beforehand
'

source ~/venvs/ludwig_venv/bin/activate
set -e

echo "Hostname: $(hostname)"

echo Launcher got args: "$@"

"$@"

# experiments: load image modality