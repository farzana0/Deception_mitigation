#!/bin/bash
set -uo pipefail
ROOT=/lambda/nfs/fs-cand-nov05
cd "$ROOT/Deception_mitigation"
export CUDA_VISIBLE_DEVICES=6 HF_HOME="$ROOT/cache/huggingface" XDG_CACHE_HOME="$ROOT/cache" TMPDIR="$ROOT/cache"
export PYTHONPATH="$ROOT/deps:$PWD:${PYTHONPATH:-}" PYTHONUNBUFFERED=1 OMP_NUM_THREADS=4 TOKENIZERS_PARALLELISM=false
python3 -m steering.cp_exploratory --phase prepare >> "$ROOT/logs/cp_prepare.log" 2>&1
status=$?
printf '%s\n' "$status" > "$ROOT/results/cp_exploratory/prepare.exitcode"
exit "$status"
