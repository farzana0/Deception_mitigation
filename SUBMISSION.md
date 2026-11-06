# CAIS provisional submission package

Open **report/report.pdf** first. This is a saved-evidence snapshot, not the final 22:00 UTC freeze. The original 240 MASK items are primary; the 819/1,000 matched expansion is partial. The 24-item scheduled/static CP comparison is a separate exploratory pilot. Live jobs were not inspected or changed because cluster tmux access was denied.

## Contents

- `report/`: PDF, editable Markdown, table CSV/JSON, figure PNG. The renderer is `experiments/code/scripts/render_submission.py`.
- `model/`: main steering fit, CP factors, locked settings, exact judge metadata and recorded environment. No base weights.
- `data/`: pinned MASK/MMLU/GSM8K saved datasets, input provenance, extraction/calibration splits, generated contrast pairs and verified item IDs.
- `experiments/`: source, pinned upstream code, run configs, saved per-item generation/judgment outputs, scoring/replay audits and source provenance. Raw logs, activation extraction checkpoints and base weights remain on the cluster.

## Reproduce saved-result tables

From the extracted package root, using Python 3.10 or newer:

```bash
python3 experiments/code/scripts/submission_tables.py --package .
```

This uses only the standard library and makes no model/judge calls. It deduplicates judgments, checks complete paired counts, verifies manifests and settings/fit hashes, recalculates capability scores from response text, checks CP disjointness, and regenerates all CSV/JSON tables. Machiavelli scores are read from the saved successful native replay audit, rather than re-running the environment.

Render the editable report with matplotlib available:

```bash
python3 experiments/code/scripts/render_submission.py --package .
```

## Table-to-source map

| Report table | Generated CSV in report/tables | Source under experiments/results |
| --- | --- | --- |
| Original MASK | mask_primary240.csv | steering_run/judge_gptoss_expanded/items.jsonl; steering_run/mask_expanded_subset.json |
| Partial expansion | mask_partial1000.csv | steering_run/judge_gptoss_full/items.jsonl; steering_run/mask_full_test_manifest.json |
| Capabilities | capabilities.csv | steering_run/capability_{condition}.jsonl |
| Machiavelli | machiavelli.csv | steering_run/machiavelli_saved_output_audit.json; machiavelli_main/{condition}/seed_{seed}/{game}/trajectory.pkl and associated output files |
| Exploratory CP | cp_exploratory.csv | cp_exploratory/pilot_judgments.jsonl; cp_exploratory/pilot_manifest.json |

MASK generation journals and judge call journals accompany the judgments. `data/verified_item_ids.json` records the IDs actually used in each regenerated table. Do not interpret marginal deception differences as paired deltas: assessable sets differ.

## Load and run each intervention

The exact base is `Qwen/Qwen3.5-9B`, revision `c202236235762e1c871ad0ccb60c8ee5ba337b9a`. The implementation uses activation hooks, BF16 SDPA, greedy decoding, seed 42 and thinking disabled. Saved results use the exact limits in the archived benchmark runners (MASK 256, MMLU 32, GSM8K 512). The generic prompt command below uses MASK's 256-token limit.

Use a CUDA host with Python 3.10 and the recorded environment in `model/hf_resolved_environment.json` and `model/hf_system_requirements.lock`. The original dependency declarations are `experiments/code/requirements.txt`. Their installation on a clean machine has **not** been validated; several packages came from the cluster's system environment. A clean GPU inference run remains a release gate.

```bash
python3 -m venv --system-site-packages .venv
. .venv/bin/activate
python3 -m pip install -r experiments/code/requirements.txt
for condition in baseline caa sttp rank2 pooled cp_scheduled cp_static; do
  CUDA_VISIBLE_DEVICES=0 python3 experiments/code/scripts/submission_infer.py \
    --package . --condition "$condition" --prompt 'What is 2 + 2?'
done
```

The runner downloads the pinned base revision using Hugging Face unless `--model-path /path/to/pinned/Qwen3.5-9B` is provided. Only load the packaged trusted `.pt` artifacts. No fine-tuned model checkpoint is produced by the experiment. Source inspection supports activation-only steering; independent local-weight-to-upstream hash verification remains pending.

The local judge is `openai/gpt-oss-20b` revision `6cee5e81ee83917806bbde320786a8fb61efebee`. Its model recipe and dependency lock are included. It must remain unsteered. No paid API calls are needed.

## Prepare portable benchmark reruns

From the package root, choose a new destination:

```bash
python3 experiments/code/scripts/prepare_submission_workspace.py \
  --package . --destination /tmp/cais-reproduction
cd /tmp/cais-reproduction/Deception_mitigation
export PYTHONPATH="$PWD"
```

This copies original code/evidence and relocates cluster path literals in the *working copy* of Python/shell files. The archived source and settings bytes stay unchanged. Historical provenance paths in JSON remain archival references. The original code commit is `3482088ed25682ae36bce26bfa26c1c3ddc6596b`; `experiments/provenance.json` records the original dirty state. Packaging scripts were added afterward.

Retrieve missing large inputs using the pinned manifest, including Machiavelli `game_data.zip` revision `3637164d9066ea3b08872fff87ce21657b6e159a`:

```bash
python3 scripts/download_inputs.py
```

The downloader reads existing pinned revisions from `results/input_manifest.json`. MASK/MMLU/GSM8K test datasets are already included. For an entirely new data download, preserve this manifest before running it. Generated contrast pairs and extraction/calibration split manifests are included. Data preparation implementations are `scripts/finalize_inputs.py`, `scripts/generate_pairs.py` and `steering/experiment.py`; do not recalibrate locked settings for reproduction.

After retrieving game data, link `../repos/simple-evals/machiavelli_eval/game_data` to `../../../data/machiavelli/extracted/game_data` if needed. Benchmark launchers and exact flags are documented in `NEXT_STAGE_REPRODUCIBILITY.md` and `NEXT_STAGE_RESUME.sh` in the working source. The latter prints commands; run only intended workers, after checking processes. Existing saved runs skip completed items. For a new replication, archive existing outputs first while retaining locked settings, fit and manifests.

```bash
CUDA_VISIBLE_DEVICES=0 python3 -m steering.capability --condition baseline
python3 scripts/audit_machiavelli.py
python3 -m unittest discover -s tests -v
```

Repeat capability conditions for caa/sttp/rank2/pooled. Full MASK generation uses `scripts/run_mask_dynamic.sh`; grading uses `scripts/grade_mask_pilot.sh` against the existing local judge. CP scripts preserve the historical pilot cutoff and should not be blindly relaunched after the deadline; generic intervention inference is available above.

## Release gates still pending

Live tmux/worker inspection; completion or deadline freeze; install this package at `/lambda/nfs/fs-cand-nov05/submission`; clean GPU inference and native Machiavelli replay; independent base-weight identity verification; final cluster archive and authorized GitHub push. This environment could not resolve github.com. Do not treat this local snapshot archive as a final frozen submission.
