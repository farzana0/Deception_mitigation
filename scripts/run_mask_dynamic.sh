#!/bin/bash
set -euo pipefail
ROOT=/lambda/nfs/fs-cand-nov05
cd "$ROOT/Deception_mitigation"
export HF_HOME="$ROOT/cache/huggingface" XDG_CACHE_HOME="$ROOT/cache" TMPDIR="$ROOT/cache"
export PYTHONPATH="$ROOT/deps:$PWD:${PYTHONPATH:-}" PYTHONUNBUFFERED=1
export OMP_NUM_THREADS=8 TOKENIZERS_PARALLELISM=false
exec python3 -u -m steering.mask_dynamic "$@"
