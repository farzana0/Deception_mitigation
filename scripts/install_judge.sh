#!/bin/bash
set -euo pipefail
ROOT=/lambda/nfs/fs-cand-nov05
export UV_CACHE_DIR="$ROOT/cache/uv" TMPDIR="$ROOT/cache" XDG_CACHE_HOME="$ROOT/cache"
/home/ubuntu/.local/bin/uv venv --python /usr/bin/python3 "$ROOT/.venv-judge"
/home/ubuntu/.local/bin/uv pip install --python "$ROOT/.venv-judge/bin/python" 'vllm==0.11.2' --torch-backend=cu128
"$ROOT/.venv-judge/bin/python" - <<'PY'
import torch,sys,json,importlib.metadata as m
from pathlib import Path
r=Path('/lambda/nfs/fs-cand-nov05')
versions={'python':sys.version,'vllm':m.version('vllm'),'torch':torch.__version__,'cuda_runtime':torch.version.cuda,'driver':'570.148.08','install_command':"uv venv --python /usr/bin/python3 /lambda/nfs/fs-cand-nov05/.venv-judge && uv pip install --python /lambda/nfs/fs-cand-nov05/.venv-judge/bin/python 'vllm==0.11.2' --torch-backend=cu128",'official_instructions':'https://docs.vllm.ai/en/v0.11.2/getting_started/installation/gpu/'}
(r/'results/steering_run/judge_environment.json').write_text(json.dumps(versions,indent=2)+'\n')
print(json.dumps(versions,indent=2))
PY
/home/ubuntu/.local/bin/uv pip freeze --python "$ROOT/.venv-judge/bin/python" > "$ROOT/results/steering_run/judge_requirements.lock"
