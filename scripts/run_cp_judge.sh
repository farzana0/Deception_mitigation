#!/bin/bash
set -uo pipefail
ROOT=/lambda/nfs/fs-cand-nov05
cd "$ROOT/Deception_mitigation"
export HF_HOME="$ROOT/cache/huggingface" XDG_CACHE_HOME="$ROOT/cache" TMPDIR="$ROOT/cache" PYTHONPATH="$ROOT/deps:$PWD:${PYTHONPATH:-}" PYTHONUNBUFFERED=1
python3 -m steering.cp_grade >> "$ROOT/logs/cp_judge.log" 2>&1
status=$?
printf '%s\n' "$status" > "$ROOT/results/cp_exploratory/judge.exitcode"
exit "$status"
