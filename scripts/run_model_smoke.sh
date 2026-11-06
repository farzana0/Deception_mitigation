#!/bin/bash
set -uo pipefail
cd /lambda/nfs/fs-cand-nov05
export HF_HOME="$PWD/cache/huggingface"
export XDG_CACHE_HOME="$PWD/cache"
export TMPDIR="$PWD/cache"
export PYTHONUNBUFFERED=1
export PYTHONPATH="$PWD/deps:${PYTHONPATH:-}"
python3 -c "from pathlib import Path; Path('results/model_smoke.exitcode').unlink(missing_ok=True)"
python3 scripts/model_smoke.py >> logs/model_smoke.log 2>&1
status=$?
printf '%s\n' "$status" > results/model_smoke.exitcode
exit "$status"
