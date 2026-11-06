#!/bin/bash
set -uo pipefail
ROOT=/lambda/nfs/fs-cand-nov05
cd "$ROOT/Deception_mitigation"
export HF_HOME="$ROOT/cache/huggingface" XDG_CACHE_HOME="$ROOT/cache" TMPDIR="$ROOT/cache"
export PYTHONPATH="$ROOT/deps:$PWD:${PYTHONPATH:-}" PYTHONUNBUFFERED=1
export OMP_NUM_THREADS=8 TOKENIZERS_PARALLELISM=false
condition=$1
shift
exec 9>"$ROOT/results/steering_run/machiavelli_${condition}.lock"
flock 9
python3 -m steering.machiavelli_local --condition "$condition" "$@" >> "$ROOT/logs/machiavelli_$condition.log" 2>&1
status=$?
printf '%s\n' "$status" > "$ROOT/results/steering_run/machiavelli_$condition.exitcode"
exit "$status"
