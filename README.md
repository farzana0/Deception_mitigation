# Deception mitigation checkpoint

Reproducible setup and shared contrast-pair generation for Qwen/Qwen3.5-9B.
This checkpoint includes project scripts, exact direct dependency versions,
pinned upstream revisions, calibration IDs, smoke-test metrics, and a small
pair-generation summary. See [REPORT.txt](REPORT.txt) for results and limitations.
No mitigation comparison has been completed yet.

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
tuning; MMLU and GSM8K test remain capability evaluations. The two steering
methods are pending specification. MT-Bench stays deferred until core
comparisons and a local judge are available.

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
credentials are excluded. No final comparative metrics or figures exist.

## Known remaining setup

`finalize_inputs.py` failed because the supplied Machiavelli archive has no
`game_data/scenarios` directory. Its existing cluster symlink is insufficient
for the official runner. Resolve this data-layout requirement before running
`python -m machiavelli_eval.machiavelli_eval` from `repos/simple-evals`.
The checked-in script preserves the failed check rather than claiming success.
MASK's official scorer and simple-evals defaults require local adapters to
keep inference and judging on this cluster. Do not invoke external API defaults.
