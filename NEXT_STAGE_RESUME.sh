#!/bin/bash
# Read commands, inspect tmux/PIDs first, then run ONLY a missing worker.
# No server restart, old coordinator, watchdog, paid APIs or automatic duplicate launch.
set -euo pipefail
cd /lambda/nfs/fs-cand-nov05/Deception_mitigation
export PYTHONPATH=/lambda/nfs/fs-cand-nov05/deps:$PWD
cat <<'COMMANDS'
# Full primary scorer (one writer, three concurrent item tasks):
MASK_JUDGE_CONCURRENCY=3 MASK_SUBSET_PATH=/lambda/nfs/fs-cand-nov05/results/steering_run/mask_full_test_manifest.json MASK_JUDGE_FOLDER=/lambda/nfs/fs-cand-nov05/results/steering_run/judge_gptoss_full bash scripts/grade_mask_pilot.sh
# Generation: use only the missing condition and its free assigned GPU, 0..4 respectively.
CUDA_VISIBLE_DEVICES=0 bash scripts/run_mask_dynamic.sh --condition baseline --activation /lambda/nfs/fs-cand-nov05/results/steering_run/mask_dynamic_activation.json
CUDA_VISIBLE_DEVICES=1 bash scripts/run_mask_dynamic.sh --condition caa --activation /lambda/nfs/fs-cand-nov05/results/steering_run/mask_dynamic_activation.json
CUDA_VISIBLE_DEVICES=2 bash scripts/run_mask_dynamic.sh --condition sttp --activation /lambda/nfs/fs-cand-nov05/results/steering_run/mask_dynamic_activation.json
CUDA_VISIBLE_DEVICES=3 bash scripts/run_mask_dynamic.sh --condition rank2 --activation /lambda/nfs/fs-cand-nov05/results/steering_run/mask_dynamic_activation.json
CUDA_VISIBLE_DEVICES=4 bash scripts/run_mask_dynamic.sh --condition pooled --activation /lambda/nfs/fs-cand-nov05/results/steering_run/mask_dynamic_activation.json
# GPU7 helper: one instance only, never overlap a static-done generation worker.
CUDA_VISIBLE_DEVICES=7 bash scripts/run_mask_dynamic.sh --helper --activation /lambda/nfs/fs-cand-nov05/results/steering_run/mask_dynamic_activation.json
# Shared main budget signal for root-owned CP gate:
python3 scripts/main_throughput_status.py
# Auxiliary workers, separate folders:
python3 -u -m steering.quality_controls --mode mask
python3 -u -m steering.quality_controls --mode capability
python3 -u -m steering.capability_assistance
python3 -u -m steering.machiavelli_quality
MASK_SUBSET_PATH=/lambda/nfs/fs-cand-nov05/results/steering_run/mask_full_test_manifest.json RESPONSE_STATUS_FOLDER=/lambda/nfs/fs-cand-nov05/results/steering_run/judge_gptoss_response_status_full RESPONSE_STATUS_WORKERS=1 python3 -u -m steering.response_status
# Fixed-state controls are complete. GPU6 is now exclusively reserved by root for CP.
# Do not resume completed fixed-state generation on GPU6; the following commands are archival only:
# CUDA_VISIBLE_DEVICES=6 python3 -u -m steering.machiavelli_counterfactual
python3 -u -m steering.machiavelli_counterfactual --judge
# Read-only evidence audit and live report, then completion validator when all workers finish:
python3 -m steering.next_stage_report
PYTHONPATH=/lambda/nfs/fs-cand-nov05/deps:$PWD python3 scripts/audit_machiavelli.py
python3 scripts/audit_next_stage.py
COMMANDS
