#!/bin/bash
set -uo pipefail
ROOT=/lambda/nfs/fs-cand-nov05
cd "$ROOT/Deception_mitigation"
export PYTHONPATH="$ROOT/deps:$PWD:${PYTHONPATH:-}" PYTHONUNBUFFERED=1
export HF_HOME="$ROOT/cache/huggingface" XDG_CACHE_HOME="$ROOT/cache" TMPDIR="$ROOT/cache"
label=gptoss
for value in "$@"; do if [[ "$value" == api ]]; then label=official_api; fi; done
python3 -m steering.grade_pilot "$@" >> "$ROOT/logs/mask_${label}_grade.log" 2>&1
status=$?
printf '%s\n' "$status" > "$ROOT/results/steering_run/judge_${label}.exitcode"
exit "$status"
