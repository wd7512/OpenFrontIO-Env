#!/usr/bin/env bash
# Apply tracked vendor patches onto the OpenFrontIO submodule checkout.
# vendor/OpenFrontIO is a pinned submodule, so local bridge fixes (replay
# behavior threading) are invisible to git; they live as patches in
# vendor-patches/ and are applied here — in CI right after
# `git submodule update --init`, and locally after a re-sync.
# --check first so a vendor pin move fails loudly instead of diverging
# replays silently (cf. OF000018, tests/test_vendor_bridge.py).
# Idempotent: patches already applied are skipped.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

for patch in vendor-patches/*.patch; do
  name="$(basename "$patch")"
  if git apply --reverse --check --directory=vendor/OpenFrontIO "$patch" 2>/dev/null; then
    echo "already applied, skipping $name"
    continue
  fi
  echo "applying $name"
  git apply --check --directory=vendor/OpenFrontIO "$patch"
  git apply --directory=vendor/OpenFrontIO "$patch"
done
echo "vendor patches applied"
