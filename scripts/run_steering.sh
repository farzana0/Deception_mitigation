#!/bin/bash
set -uo pipefail
ROOT=/lambda/nfs/fs-cand-nov05
cd "$ROOT/Deception_mitigation"
export HF_HOME="$ROOT/cache/huggingface" XDG_CACHE_HOME="$ROOT/cache" TMPDIR="$ROOT/cache"
export PYTHONPATH="$ROOT/deps:$PWD:${PYTHONPATH:-}" PYTHONUNBUFFERED=1
export OMP_NUM_THREADS=8 TOKENIZERS_PARALLELISM=false
python3 -c "from pathlib import Path; Path('$ROOT/results/steering_run/experiment${STEERING_EVAL_CONDITIONS:-}.exitcode').unlink(missing_ok=True)"
python3 -m steering.experiment "$@" >> "$ROOT/logs/steering_experiment${STEERING_EVAL_CONDITIONS:-}.log" 2>&1
status=$?
printf '%s\n' "$status" > "$ROOT/results/steering_run/experiment${STEERING_EVAL_CONDITIONS:-}.exitcode"
exit "$status"
