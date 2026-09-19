#!/usr/bin/env bash
# run.sh — dry-run wrapper for the keyless lit-review batch.
# Usage: bash run.sh [--start N] [--end N] [--concurrency N] [...]
# Live runs are refused by run.py (keyless policy); this wrapper always
# defaults to --dry-run unless --no-dry-run/--live is passed through.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BATCH_DIR="$(dirname "$SCRIPT_DIR")"
ITER1_DIR="$(dirname "$BATCH_DIR")"
REPORTS_DIR="$BATCH_DIR/reports"
mkdir -p "$REPORTS_DIR"

exec python3 "$SCRIPT_DIR/run.py" \
    --questions "$ITER1_DIR/research-questions.md" \
    --proposal "$ITER1_DIR/proposal.md" \
    --reports-dir "$REPORTS_DIR" \
    --dry-run \
    "$@"
