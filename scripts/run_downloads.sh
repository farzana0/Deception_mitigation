#!/bin/bash
set -uo pipefail
cd /lambda/nfs/fs-cand-nov05
export HF_HOME="$PWD/cache/huggingface"
export XDG_CACHE_HOME="$PWD/cache"
export TMPDIR="$PWD/cache"
export PYTHONPATH="$PWD/deps:${PYTHONPATH:-}"
export PYTHONUNBUFFERED=1
python3 scripts/download_inputs.py >> logs/download_inputs.log 2>&1
status=$?
printf '%s\n' "$status" > results/download_inputs.exitcode
exit "$status"
