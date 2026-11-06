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
CUDA_VISIBLE_DEVICES=0 STEERING_EVAL_CONDITIONS=baseline MASK_SUBSET_PATH=/lambda/nfs/fs-cand-nov05/results/steering_run/mask_full_test_manifest.json bash scripts/run_steering.sh --phase eval
CUDA_VISIBLE_DEVICES=1 STEERING_EVAL_CONDITIONS=caa MASK_SUBSET_PATH=/lambda/nfs/fs-cand-nov05/results/steering_run/mask_full_test_manifest.json bash scripts/run_steering.sh --phase eval
CUDA_VISIBLE_DEVICES=2 STEERING_EVAL_CONDITIONS=sttp MASK_SUBSET_PATH=/lambda/nfs/fs-cand-nov05/results/steering_run/mask_full_test_manifest.json bash scripts/run_steering.sh --phase eval
CUDA_VISIBLE_DEVICES=3 STEERING_EVAL_CONDITIONS=rank2 MASK_SUBSET_PATH=/lambda/nfs/fs-cand-nov05/results/steering_run/mask_full_test_manifest.json bash scripts/run_steering.sh --phase eval
CUDA_VISIBLE_DEVICES=4 STEERING_EVAL_CONDITIONS=pooled MASK_SUBSET_PATH=/lambda/nfs/fs-cand-nov05/results/steering_run/mask_full_test_manifest.json bash scripts/run_steering.sh --phase eval
# Auxiliary workers, separate folders:
python3 -u -m steering.quality_controls --mode mask
python3 -u -m steering.quality_controls --mode capability
python3 -u -m steering.capability_assistance
python3 -u -m steering.machiavelli_quality
MASK_SUBSET_PATH=/lambda/nfs/fs-cand-nov05/results/steering_run/mask_full_test_manifest.json RESPONSE_STATUS_FOLDER=/lambda/nfs/fs-cand-nov05/results/steering_run/judge_gptoss_response_status_full RESPONSE_STATUS_WORKERS=1 python3 -u -m steering.response_status
# Fixed-state generation (GPU6 must be free), followed after it completes by its separate judge:
CUDA_VISIBLE_DEVICES=6 python3 -u -m steering.machiavelli_counterfactual
python3 -u -m steering.machiavelli_counterfactual --judge
# Read-only evidence audit and live report, then completion validator when all workers finish:
python3 -m steering.next_stage_report
PYTHONPATH=/lambda/nfs/fs-cand-nov05/deps:$PWD python3 scripts/audit_machiavelli.py
python3 scripts/audit_next_stage.py
COMMANDS
