# Agent instructions

Read README.md first. It has the layout and the three reproduction paths.

## Rules

- Do not change reported results. `results/frozen/`, `evidence/`, `models/steering_fits/`, `models/locked/` and
  `data/manifests/` are frozen inputs and targets. `python -m cais task=rebuild` must still pass with exit 0 after any change.
- Do not recalibrate. Intervention YAMLs must equal `models/locked/*.json`, and the CLI asserts this at start-up.
- Keep `steering/` and `scripts/` behaviour unchanged. They are the code that produced the evidence. Add new
  behaviour in `cais/`, as plain functions, without silent fallbacks. Fail loudly on missing or inconsistent inputs.
- Configuration belongs in `conf/<group>/<name>.yaml`. Do not add CLI flags or environment variables outside Hydra,
  except the ones the library already reads (set in `cais/cli.py`).
- Runs write only under `outputs/`, which is git-ignored. Every run saves `resolved_config.yaml`. Use a new
  `paths.outputs` for an independent rerun. Never point a run at another experiment's directory.
- Shared machine: check `nvidia-smi` and `tmux ls` before using a GPU. Use only idle GPUs. Never stop other workers or
  the judge server on `127.0.0.1:8001`.
- No paid API calls. The judge is local and must remain unsteered.
- Scratch notes, drafts and status summaries do not belong in this repository. Keep them outside the git tree.
- Before committing, run:
  `python -m unittest tests.test_cli` and `python -m cais task=rebuild`.
