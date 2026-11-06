#!/bin/bash
set -uo pipefail
ROOT=/lambda/nfs/fs-cand-nov05
cd "$ROOT/Deception_mitigation"
gpu=$1
condition=$2
while tmux has-session -t "mask-expanded-$condition" 2>/dev/null; do
    sleep 60
done
while [[ $(nvidia-smi --id="$gpu" --query-gpu=memory.used --format=csv,noheader,nounits) -gt 100 ]]; do
    sleep 60
done
printf '%s Starting %s on GPU %s after MASK generation\n' "$(date -u +%FT%TZ)" "$condition" "$gpu"
CUDA_VISIBLE_DEVICES="$gpu" bash scripts/run_machiavelli.sh "$condition" --output-name machiavelli_main --seeds 0,1 --game-count 2 --max-steps 150
