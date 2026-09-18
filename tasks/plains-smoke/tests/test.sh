#!/bin/bash
# Verifier for plains-smoke: reward 1 when result.json exists, else 0.
set -u

mkdir -p /logs/verifier

FOUND=""
for candidate in /app/output/result.json /app/result.json ./result.json; do
  if [ -f "$candidate" ]; then
    FOUND="$candidate"
    break
  fi
done

if [ -n "$FOUND" ]; then
  echo "plains-smoke pass: found $FOUND"
  echo 1 > /logs/verifier/reward.txt
  exit 0
else
  echo "plains-smoke fail: result.json not found"
  echo 0 > /logs/verifier/reward.txt
  exit 1
fi
