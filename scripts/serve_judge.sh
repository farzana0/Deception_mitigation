#!/bin/bash
set -euo pipefail
ROOT=/lambda/nfs/fs-cand-nov05
cd "$ROOT"
export HF_HOME="$ROOT/cache/huggingface" XDG_CACHE_HOME="$ROOT/cache" TMPDIR="$ROOT/cache"
export CUDA_VISIBLE_DEVICES=5 OMP_NUM_THREADS=8 VLLM_ATTENTION_BACKEND=TRITON_ATTN
export VLLM_NO_USAGE_STATS=1 DO_NOT_TRACK=1 HF_HUB_DISABLE_TELEMETRY=1
export TORCHINDUCTOR_CACHE_DIR="$ROOT/cache/torchinductor-judge" TRITON_CACHE_DIR="$ROOT/cache/triton-judge"
unset PYTHONPATH
while [[ ! -f "$ROOT/results/steering_run/judge_environment.json" || ! -f "$ROOT/results/steering_run/judge_download.complete" ]]; do sleep 10; done
"$ROOT/.venv-judge/bin/python" - <<'PY'
import json,subprocess
from pathlib import Path
r=Path('/lambda/nfs/fs-cand-nov05')
cmd=[str(r/'.venv-judge/bin/vllm'),'serve',str(r/'models/gpt-oss-20b'),'--served-model-name','openai/gpt-oss-20b','--host','127.0.0.1','--port','8001','--tensor-parallel-size','1','--dtype','bfloat16','--gpu-memory-utilization','0.8','--max-model-len','8192','--max-num-seqs','8','--enforce-eager','--reasoning-parser','openai_gptoss','--disable-log-requests']
record={'command':cmd,'gpu_index':5,'gpu':subprocess.check_output(['nvidia-smi','--id=5','--query-gpu=uuid,name,driver_version','--format=csv,noheader'],text=True).strip(),'model':json.loads((r/'results/steering_run/judge_model.json').read_text()),'host':'127.0.0.1','reasoning_effort':'low (set on each request)','attention_backend':'TRITON_ATTN'}
(r/'results/steering_run/judge_launch.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2),flush=True)
import os
os.execv(cmd[0],cmd)
PY
