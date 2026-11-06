#!/bin/bash
set -uo pipefail
ROOT=/lambda/nfs/fs-cand-nov05
cd "$ROOT/Deception_mitigation"
export PYTHONPATH="$ROOT/deps:$PWD:${PYTHONPATH:-}" PYTHONUNBUFFERED=1
while [[ $(date -u +%s) -lt 1793964600 ]]; do
    python3 -m steering.overnight_report
    sleep 60
done
