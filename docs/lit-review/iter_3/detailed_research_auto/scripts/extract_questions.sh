#!/usr/bin/env bash
# extract_questions.sh — print numbered research questions as N|text.
# Usage: bash extract_questions.sh [questions-file]
set -euo pipefail

QUESTIONS_FILE="${1:-$(dirname "$0")/../../detailed_research_questions.md}"

if [[ ! -f "$QUESTIONS_FILE" ]]; then
    echo "ERROR: questions file not found: $QUESTIONS_FILE" >&2
    exit 1
fi

grep -E '^[[:space:]]*[0-9]+\.[[:space:]]+' "$QUESTIONS_FILE" \
    | sed -E 's/^[[:space:]]*([0-9]+)\.[[:space:]]+/\1|/'
