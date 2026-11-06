#!/bin/bash
set -uo pipefail
cd /lambda/nfs/fs-cand-nov05
export HF_HOME="$PWD/cache/huggingface" XDG_CACHE_HOME="$PWD/cache" TMPDIR="$PWD/cache"
export PYTHONPATH="$PWD/deps:${PYTHONPATH:-}" PYTHONUNBUFFERED=1
python3 scripts/generate_pairs.py >> logs/contrast_pairs.log 2>&1
status=$?
printf '%s\n' "$status" > results/contrast_pairs.exitcode
exit "$status"
