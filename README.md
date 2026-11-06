# Activation steering for honesty (CAIS)

Inference-time residual steering of `Qwen/Qwen3.5-9B` (revision `c2022362…`) to reduce deception, evaluated on the
1,000-item MASK cohort with an unsteered local `openai/gpt-oss-20b` judge using the official MASK rubric, plus small
MMLU/GSM8K capability pilots, a 20-trajectory Machiavelli pilot and an exploratory CP comparison.

Five main conditions: `baseline`, `caa` (layer 16, strength 0.1), `sttp` (layer 20, c=2), `rank2` (strength 0.1),
`pooled` (strength 0.1). Settings were locked on 10 calibration scenarios before any held-out evaluation.

Main result (full MASK cohort, 1,000 matched items; deception = dishonest / assessable; lower is better):

| Condition | Assessable | Dishonest | Deception | Paired Δ vs baseline |
| --- | ---: | ---: | ---: | ---: |
| baseline | 729 | 441 | 60.49% | — |
| caa | 741 | 421 | 56.82% | −3.05 pp (n=656) |
| sttp | 739 | 451 | 61.03% | +0.75 pp (n=666) |
| rank2 | 728 | 420 | 57.69% | −1.24 pp (n=643) |
| pooled | 729 | 423 | 58.02% | −2.52 pp (n=634) |

All frozen tables are in [`results/frozen/tables/`](results/frozen/tables/) and the report in
[`results/frozen/report.pdf`](results/frozen/report.pdf). The results do not establish a general reduction in deception;
read the report's limitations before citing numbers.

## Layout

| Path | Contents |
| --- | --- |
| `cais/` | The Hydra CLI (`python -m cais`). Thin layer over the existing code below. |
| `conf/` | One YAML per `model`, `intervention`, `dataset`, `judge_model`, `judge_rubric`, plus `task`. |
| `steering/`, `scripts/` | Experiment library and scripts that produced the results (inference, steering hooks, judging, scoring, tables, report rendering). |
| `data/manifests/` | Item manifests (MASK 1000/240/12/6, CP 24), extraction/calibration split, pinned input revisions. |
| `data/contrast_pairs/`, `data/dataset_info/` | Generated contrast pairs used for the fit; MMLU/GSM8K split sizes. |
| `models/` | Model revisions and weight locations ([models/README.md](models/README.md)), steering fits, locked settings, judge identity. |
| `evidence/` | Saved per-item outputs from the verified submission (generations, judge items and calls, capability, CP, Machiavelli audit), gzip-compressed, with SHA256 in `evidence/MANIFEST.json`. |
| `results/` | Curated results: `frozen/` (tables, figures, report from the verified submission), `paired_examples/`, `figure_data/`, `verification/`. |
| `reproduction/` | Auxiliary reproduction files: protocols, original run configs and summaries, provenance, cluster launch notes, submission verification record. |
| `tools/` | One-time import of evidence from the frozen submission. |
| `tests/` | Unit tests. |
| `outputs/` | Run outputs (git-ignored). Every run writes `hydra/<time>_<task>_<intervention>/resolved_config.yaml`. |

## Setup

Python 3.10. The offline rebuild needs only `requirements-rebuild.txt`. GPU runs use the recorded cluster
environment: system `torch==2.7.0` (do not reinstall), `requirements.txt`, an A100 80 GB, and the judge in its own
vLLM 0.11.2 environment (`models/judge/judge_requirements.lock`).

```bash
git clone -b refactor git@github.com:farzana0/Deception_mitigation.git && cd Deception_mitigation
python3 -m venv .venv-rebuild && .venv-rebuild/bin/pip install -r requirements-rebuild.txt
```

## 1. Offline rebuild from saved evidence (no GPU, ~10 s)

```bash
.venv-rebuild/bin/python -m cais task=rebuild
```

This verifies every evidence file against `evidence/MANIFEST.json`, rebuilds the submission layout under
`outputs/rebuild/package/`, and reruns the original `scripts/submission_tables.py` and `scripts/render_submission.py`.
It then writes the 12-item paired prompt/response examples and figure data, and compares everything with the frozen
copies. It exits non-zero on any difference in tables, item IDs, `report.md`, figure data (bar heights) or examples.
PNG bytes depend on the FreeType build used for text antialiasing, so `verification.json` reports them separately.
They are byte-identical with Ubuntu's matplotlib 3.5.1 and FreeType 2.11.1. The pip wheel bundles FreeType 2.6.1,
which changes text antialiasing (1–2% of pixels) but not the plotted data.

| Output | Path |
| --- | --- |
| Tables (CSV/JSON) | `outputs/rebuild/outputs/tables/` |
| Figures and report pages | `outputs/rebuild/outputs/figures/`, `outputs/rebuild/outputs/report.{md,pdf}` |
| Paired examples | `outputs/rebuild/paired_examples/paired_examples.{md,jsonl}` |
| Figure data | `outputs/rebuild/figure_data/mask_main.csv` |
| Check results | `outputs/rebuild/verification.json` |

## 2. Quick fresh rerun on a fixed subset (1 GPU + judge, ~1 h)

`mask_quick6` is the first item per MASK configuration of the 12-item pilot manifest. Those pilot items are the two
lowest `SHA256(config + task_id)` items per configuration over the full test split, so the selection does not depend on
outcomes. Decoding is greedy, `torch.manual_seed(42)`, thinking disabled, 256 new tokens. The judge uses temperature 0,
seed 42, and low reasoning effort.

| Config | Task ID |
| --- | --- |
| continuations | `6774a05e18ea0dba85f905e3` |
| disinformation | `67771717dd7a1c86eaf48ae7` |
| doubling_down_known_facts | `67975edbe260b367c78ca07f` |
| known_facts | `677d553a0e75fcaf2976f9c2` |
| provided_facts | `67ab8fa3145008ba956213c3` |
| statistics | `678992767c26e3533f441684` |

Prerequisites: base weights at `model.local_dir`, the MASK test splits under `paths.data_root`, and the pinned MASK
checkout under `paths.repos_root`. All three default to `/lambda/nfs/fs-cand-nov05` (see section 3 to create them
elsewhere). The judge must be serving on `127.0.0.1:8001`; see `conf/judge_model/gpt_oss_20b.yaml` (`serve`) or
`scripts/serve_judge.sh`.

```bash
export PYTHONPATH=$PWD HF_HUB_OFFLINE=1 CUDA_VISIBLE_DEVICES=0
python -m cais -m task=generate dataset=mask_quick6 intervention=baseline,caa,sttp,rank2,pooled
python -m cais task=judge  dataset=mask_quick6
python -m cais task=report dataset=mask_quick6
```

Outputs in `outputs/runs/mask_quick6/`:

- `steering_run/mask_generations_<intervention>.jsonl`: generations.
- `steering_run/judge/{items,calls}.jsonl`: judgments.
- `report/mask_table.csv`: table.
- `report/mask_deception.png` and `report/figure_data.csv`: figure.
- `report/paired_examples.md`: paired examples.
- `report/comparison.json`: token-level and label-level comparison with the saved evidence.

Runs resume from their journals. Use a new `paths.outputs=...` for an independent rerun.

## 3. Full evaluation

Inputs (once per machine). `CAIS_ROOT` is the large-input root, the same as `paths.cluster_root`:

```bash
export CAIS_ROOT=/lambda/nfs/fs-cand-nov05     # or any large disk
mkdir -p $CAIS_ROOT/{models,data,repos,results}
cp data/manifests/input_manifest.json $CAIS_ROOT/results/  # pins dataset and upstream revisions
python scripts/download_inputs.py                          # MASK/MMLU/GSM8K test splits, upstream repos, Machiavelli game data
python -c "from huggingface_hub import snapshot_download as d; d('Qwen/Qwen3.5-9B', revision='c202236235762e1c871ad0ccb60c8ee5ba337b9a', local_dir='$CAIS_ROOT/models/Qwen3.5-9B'); d('openai/gpt-oss-20b', revision='6cee5e81ee83917806bbde320786a8fb61efebee', local_dir='$CAIS_ROOT/models/gpt-oss-20b')"
python scripts/verify_base_weights.py --model-dir $CAIS_ROOT/models/Qwen3.5-9B --output outputs/base_weight_verification.json
```

For Machiavelli, link `$CAIS_ROOT/repos/simple-evals/machiavelli_eval/game_data` to
`$CAIS_ROOT/data/machiavelli/extracted/game_data` (see `scripts/finalize_inputs.py`). Start the judge in its own
environment on one GPU (`scripts/serve_judge.sh` shows the exact launch).

Runs. Add `paths.cluster_root=$CAIS_ROOT` if it is not the default. Each intervention can run on its own GPU in
parallel because they write separate journals in the same run directory.

```bash
export PYTHONPATH=$PWD HF_HUB_OFFLINE=1
# MASK, 1,000 items x 5 interventions
for iv in baseline caa sttp rank2 pooled; do
  CUDA_VISIBLE_DEVICES=<gpu> python -m cais task=generate dataset=mask_full1000 intervention=$iv
done
python -m cais task=judge  dataset=mask_full1000 judge_model.concurrency=3
python -m cais task=report dataset=mask_full1000
# Capability pilots (MMLU 30 + GSM8K 10) and Machiavelli (2 games x seeds 0,1, 150 steps)
CUDA_VISIBLE_DEVICES=<gpu> python -m cais -m task=generate dataset=capability_pilot intervention=baseline,caa,sttp,rank2,pooled
CUDA_VISIBLE_DEVICES=<gpu> python -m cais -m task=generate dataset=machiavelli_main intervention=baseline,caa,sttp,rank2,pooled
# Single prompt, including the exploratory CP hooks
CUDA_VISIBLE_DEVICES=<gpu> python -m cais task=infer intervention=cp_scheduled task.prompt='What is 2 + 2?'
```

Output paths:

| Run | Directory |
| --- | --- |
| MASK | `outputs/runs/mask_full1000/` (`steering_run/`, `report/`) |
| Capability | `outputs/runs/capability_pilot/steering_run/capability_<intervention>.jsonl` |
| Machiavelli | `outputs/runs/machiavelli_main/steering_run/machiavelli_main/<intervention>/seed_<s>/<game>/` |
| Inference | `outputs/infer/<intervention>/hydra/*/result.json` |

Steering fit extraction and calibration are not rerun; the locked fit and settings are inputs. Their generating code is
`steering/experiment.py` (`--phase extract|calibrate`), with the frozen copy in `models/locked/locked_experiment.py`.

Evidence audit of the frozen package: pinned official MASK aggregation, judge-response parsing and
generation-to-judge linkage. This needs the frozen submission directory, which includes the datasets.

```bash
python -m cais task=audit task.package=/home/ubuntu/cais_work/submission
```

## What was verified

| Command | Status |
| --- | --- |
| 1. `task=rebuild` from a clean clone in a fresh venv | **Verified.** See `results/verification/rebuild_clean_checkout.json` |
| 2. `task=generate/judge/report dataset=mask_quick6` | See `results/verification/quick6/` |
| 3. Full evaluation, capability, Machiavelli, `task=infer`, `task=audit` | Documented only, not rerun in this refactor. The original outputs are the saved evidence. |
| `python -m unittest tests.test_cli` | Verified (config composition, locked settings, manifests, evidence hashes) |

## Conventions

- Each YAML is checked against the locked artifacts at start-up (`cais/workspace.py:check_locked`): intervention
  settings against `models/locked/`, fit hashes, model, judge and rubric revisions.
- `steering/` and `scripts/` are the code that produced the results. The refactor changed only the path of the MASK pin
  file in `steering/official_mask.py` and made the `scripts/download_inputs.py` root overridable with `CAIS_ROOT`.
- MASK technical judge failures are distinct from valid "unknown" (C/D or null) outcomes. Deception uses only assessable
  items. Paired deltas use items assessable under both conditions.
- No paid API calls. The judge is local and never steered.
