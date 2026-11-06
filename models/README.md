# Models

| Role | Model | Revision | Weights (not in git) | Config |
| --- | --- | --- | --- | --- |
| Steered base | `Qwen/Qwen3.5-9B` | `c202236235762e1c871ad0ccb60c8ee5ba337b9a` | `/lambda/nfs/fs-cand-nov05/models/Qwen3.5-9B` | `conf/model/qwen3_5_9b.yaml` |
| Judge (never steered) | `openai/gpt-oss-20b` | `6cee5e81ee83917806bbde320786a8fb61efebee` | `/lambda/nfs/fs-cand-nov05/models/gpt-oss-20b` | `conf/judge_model/gpt_oss_20b.yaml` |

Override the weight location with `model.local_dir=...` or `paths.cluster_root=...`.
The experiment never trains or modifies base weights; interventions are inference-time residual hooks.

## Base-weight shards (SHA256 matches the cached Hugging Face LFS digests)

| File | Bytes | SHA256 |
| --- | ---: | --- |
| `model.safetensors-00001-of-00004.safetensors` | 5,276,436,216 | `db6f444b43d318c92f360a13a25561a6a65b10c0631b8ed305a426dbaa6c380e` |
| `model.safetensors-00002-of-00004.safetensors` | 5,335,161,512 | `31c7d7e2dd5d207840b31cc59083c8f4c4718959149e0358c0364052bb9a0330` |
| `model.safetensors-00003-of-00004.safetensors` | 5,368,717,440 | `7ec36ba3a4176a44c3c0876ad80c56a2f70c84bf008d82e9501df642f17dadec` |
| `model.safetensors-00004-of-00004.safetensors` | 3,325,995,712 | `b62b0c4cd7e44edee103ee8f4fe225f246d5e768e07bfd5f25b63a8aa1fdd0c6` |

Recheck: `python scripts/verify_base_weights.py --model-dir <dir> --output base_weight_verification.json`.

## Contents

| Path | What |
| --- | --- |
| `steering_fits/fit.pt` | Main steering fit: CAA directions, StTP probes, rank-2 and pooled schedules, residual norms (layers 8, 12, 16, 20, 24) |
| `steering_fits/cp_fit.pt` | Exploratory CP scheduled/static schedules |
| `locked/locked_settings.json` | Calibration-locked settings for baseline, caa, sttp, rank2, pooled plus fit/pairs/splits/source hashes |
| `locked/locked_cp_settings.json`, `locked/cp_predeclared_protocol.json` | Exploratory CP lock and protocol |
| `locked/locked_experiment.py` | Frozen copy of `steering/experiment.py` that produced the fit and calibration |
| `judge/` | Judge identity (part of every cached request id) and the isolated vLLM 0.11.2 dependency lock |
| `base/` | Base-weight verification and the recorded Hugging Face environment |

Load these `.pt` files only from this trusted repository (`torch.load(..., weights_only=False)`).
