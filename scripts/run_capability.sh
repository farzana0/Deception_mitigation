#!/bin/bash
set -uo pipefail
ROOT=/lambda/nfs/fs-cand-nov05
cd "$ROOT/Deception_mitigation"
export HF_HOME="$ROOT/cache/huggingface" XDG_CACHE_HOME="$ROOT/cache" TMPDIR="$ROOT/cache"
export PYTHONPATH="$ROOT/deps:$PWD:${PYTHONPATH:-}" PYTHONUNBUFFERED=1
export OMP_NUM_THREADS=8 TOKENIZERS_PARALLELISM=false
python3 -m steering.capability --condition "$1" >> "$ROOT/logs/capability_$1.log" 2>&1
status=$?
printf '%s\n' "$status" > "$ROOT/results/steering_run/capability_$1.exitcode"
exit "$status"
