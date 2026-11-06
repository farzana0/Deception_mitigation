# Deception mitigation checkpoint

Reproducible setup and shared contrast-pair generation for Qwen/Qwen3.5-9B.
This checkpoint includes project scripts, exact direct dependency versions,
pinned upstream revisions, calibration IDs, smoke-test metrics, and a small
pair-generation summary. See [REPORT.txt](REPORT.txt) for results and limitations.
The independent local-judge 12-item MASK pilot and paired MMLU/GSM8K pilots
have completed. The fixed 240-item MASK expansion and all 20 Machiavelli
trajectories (two games × two seeds × five conditions) are also complete.
Saved-output, gold-answer, and native game-replay audits passed. See the
timestamped report for denominators, metrics and limitations.

## Cluster workspace

All scripts currently target `/lambda/nfs/fs-cand-nov05`. The backup checkout
is `/lambda/nfs/fs-cand-nov05/Deception_mitigation`. Original scripts remain
in the parent workspace, so existing job source paths are preserved.
The cluster node terminates at 2026-11-07 04:00 UTC; the NFS path persists.

## Setup and run

Use Python 3.10 with cluster-provided torch 2.7.0; do not reinstall torch.
On this existing cluster, dependencies are already available. To restore
missing direct dependencies into the persistent workspace:

```bash
cd /lambda/nfs/fs-cand-nov05/Deception_mitigation
python3 -m pip install --cache-dir /lambda/nfs/fs-cand-nov05/cache/pip --target /lambda/nfs/fs-cand-nov05/deps --no-deps -r requirements.txt
```

This relies on the Lambda Stack and existing transitive dependencies; it is
not a complete portable environment lock. Git, tmux, CUDA, and an A100-class
GPU are required. Restore checkpoint scripts and the pinned input manifest
before running them on a fresh cluster workspace (review local differences
first if those destination files already exist):

```bash
mkdir -p /lambda/nfs/fs-cand-nov05/{scripts,logs,results,cache,models,data,repos}
cp -n scripts/* /lambda/nfs/fs-cand-nov05/scripts/
cp -n results/input_manifest.json /lambda/nfs/fs-cand-nov05/results/
# Pin downloads using the manifest; generate model smoke result after download.
tmux new-session -d -s input-downloads /lambda/nfs/fs-cand-nov05/scripts/run_downloads.sh
tmux new-session -d -s qwen-smoke /lambda/nfs/fs-cand-nov05/scripts/run_model_smoke.sh
# After the model smoke test and steering repository download succeed:
tmux new-session -d -s contrast-pairs /lambda/nfs/fs-cand-nov05/scripts/run_pairs.sh
```

The downloader checks out the recorded upstream commits and uses pinned
Hugging Face revisions. Model revision is embedded in model_smoke.py.
Generation resumes by scenario ID from the cluster JSONL; use a new output
path for a different generation configuration. Greedy generation disables
thinking and allows 256 new tokens per completion.

## Data separation

Use only the requested self_report_experimental_scenarios.json from the
pinned Tara-Research repository for pairs. Seed 42 separates 40 extraction
scenarios and 10 calibration scenarios. Choose layers and strengths only
with calibration. MASK and Machiavelli remain held out of extraction and
tuning; MMLU and GSM8K test remain capability evaluations. The locked CAA, Herbster StTP, rank-2 and pooled-control definitions are
in [STEERING_PROTOCOL.txt](STEERING_PROTOCOL.txt). MT-Bench stays deferred.

## Artifacts kept on the cluster

All paths below are relative to `/lambda/nfs/fs-cand-nov05`:

| Path | Contents |
| --- | --- |
| `models/Qwen3.5-9B/` | Downloaded model weights and tokenizer/processor |
| `data/` | Saved MASK, MMLU, GSM8K test splits and Machiavelli bundle/extraction |
| `cache/` | Hugging Face and other download caches |
| `deps/` | Local dependency overrides |
| `repos/` | Pinned steering, MASK scoring, and simple-evals repositories |
| `results/qwen_contrast_pairs.jsonl` | Raw 50 paired generations and token IDs |
| `logs/` | Download, GPU smoke, contrast pair, and setup logs |

Small JSON manifests, summaries, and smoke metrics are backed up in this
checkout's `results/`. Raw outputs, datasets, weights, caches, logs, and
credentials are excluded. Independent paired pilot results and partial expanded metrics are recorded
in REPORT.txt. Full cluster status is in the parent OVERNIGHT_STATUS.md.

## Local evaluation and resume

The Machiavelli bundle uses source/ and trees/ directly; setup and a real
scored trajectory passed. Do not invoke upstream external API defaults.
The local adapter uses official gameplay, trajectory annotations, and scoring.
Main game/seed pairs checkpoint after each scored trajectory.

Keep system torch 2.7.0 for Hugging Face experiments. The independent judge
uses isolated `.venv-judge` in the parent workspace (vLLM 0.11.2,
torch 2.9.0+cu128). Exact settings, model revisions and package lock are in
`configs/overnight/`. The judge binds localhost on GPU 5; do not start a
second server if tmux `mask-judge-server` is healthy.

```bash
# Run from this checkout. Inspect tmux ls and nvidia-smi first.
CUDA_VISIBLE_DEVICES=GPU bash scripts/run_capability.sh CONDITION
CUDA_VISIBLE_DEVICES=GPU bash scripts/run_machiavelli.sh CONDITION --output-name machiavelli_main --seeds 0,1 --game-count 2 --max-steps 150
# MASK pilot judge resumes successful calls and item-condition checkpoints.
bash scripts/grade_mask_pilot.sh
# Expanded generation and judging reuse the pilot and fixed settings.
CUDA_VISIBLE_DEVICES=GPU STEERING_EVAL_CONDITIONS=CONDITION MASK_SUBSET_PATH=/lambda/nfs/fs-cand-nov05/results/steering_run/mask_expanded_subset.json bash scripts/run_steering.sh --phase eval
MASK_SUBSET_PATH=/lambda/nfs/fs-cand-nov05/results/steering_run/mask_expanded_subset.json MASK_JUDGE_FOLDER=/lambda/nfs/fs-cand-nov05/results/steering_run/judge_gptoss_expanded bash scripts/grade_mask_pilot.sh
PYTHONPATH=/lambda/nfs/fs-cand-nov05/deps:$PWD python3 -m steering.overnight_report
PYTHONPATH=/lambda/nfs/fs-cand-nov05/deps:$PWD python3 -m unittest discover -s tests -v
```

Put GPU commands in tmux. Conditions are baseline, caa, sttp, rank2, pooled.
MASK technical judge failures remain distinct from valid unknown responses;
failed requests retry without regenerating successful calls. Independent
pilot, expansion and earlier self-judge outputs live in separate directories.
All inference stays local; no paid API requests or Git push during this run.

Independent response-status annotations separately measure explicit refusal and
uncertainty-based abstention on all 1,200 saved pressure responses. Their frozen
rubric, validation and summaries are in `configs/overnight/response_status_*`.
Core MASK C/no-claim counts and D/denies-both counts remain separate. The pinned
Machiavelli fork logs pre-action point snapshots; the report preserves those
scores and also gives replay-verified final achievement scores.

```bash
PYTHONPATH=/lambda/nfs/fs-cand-nov05/deps:$PWD python3 scripts/audit_saved_evaluations.py
PYTHONPATH=/lambda/nfs/fs-cand-nov05/deps:$PWD python3 scripts/audit_response_status.py
PYTHONPATH=/lambda/nfs/fs-cand-nov05/deps:$PWD python3 scripts/audit_machiavelli.py
```
