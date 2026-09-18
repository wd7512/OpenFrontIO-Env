#!/usr/bin/env bash
# run.sh — dry-run wrapper for the T6 keyless lit-review batch.
# Usage: bash run.sh [--start N] [--end N] [--concurrency N] [...]
# Live runs are refused by run.py (keyless policy); this wrapper always
# defaults to --dry-run unless --no-dry-run/--live is passed through.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AUTO_DIR="$(dirname "$SCRIPT_DIR")"
ITER3_DIR="$(dirname "$AUTO_DIR")"
LIT_DIR="$(dirname "$ITER3_DIR")"
REPORTS_DIR="$AUTO_DIR/reports"
mkdir -p "$REPORTS_DIR"

exec python3 "$SCRIPT_DIR/run.py" \
    --questions "$ITER3_DIR/detailed_research_questions.md" \
    --proposal "$LIT_DIR/iter_1/proposal_v1.md" \
    --prompts-dir "$ITER3_DIR/research-prompts" \
    --reports-dir "$REPORTS_DIR" \
    --dry-run \
    "$@"
