#!/usr/bin/env bash
# Build the reproducible openfront-env base image for linux/amd64.
#
# Pattern ported from custom-harbor/scripts/build-amd64.sh: explicit
# `docker buildx` platform build, `--load` into the local daemon, then a
# host-side `docker inspect` arch guard (sufficient because the image is
# consumed locally, never pushed).
#
# Usage: scripts/build-openfront.sh [--tag <tag>] [--dry-run]
# Env: IMAGE (default openfront-env), TAG (default: git short SHA, else local).
#
# Images are local-only by policy: this script has no push path and refuses
# push-related arguments. Promotion to a registry is a separate step (T2).

set -euo pipefail

IMAGE="${IMAGE:-openfront-env}"
TAG="${TAG:-}"
DRY_RUN=0

usage() {
  echo "usage: $0 [--tag <tag>] [--dry-run]" >&2
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --tag)
      TAG="${2:?--tag needs a value}"
      shift 2
      ;;
    --tag=*)
      TAG="${1#--tag=}"
      shift
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    *push*)
      echo "refusing push-related argument '$1': images are local-only (no-push policy)" >&2
      exit 1
      ;;
    *)
      echo "unknown argument '$1'" >&2
      usage
      exit 1
      ;;
  esac
done

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DOCKERFILE="$REPO_ROOT/docker/openfront/Dockerfile"
if [ ! -f "$DOCKERFILE" ]; then
  echo "FATAL: Dockerfile not found at $DOCKERFILE" >&2
  exit 1
fi

if [ -z "$TAG" ]; then
  if git -C "$REPO_ROOT" rev-parse --short HEAD >/dev/null 2>&1; then
    TAG="$(git -C "$REPO_ROOT" rev-parse --short HEAD)"
  else
    TAG="local"
  fi
fi
REF="${IMAGE}:${TAG}"

# The submodule must be initialized: an empty vendor dir would build a broken
# bundle. (An uninitialized submodule has no .git entry of its own.)
if [ ! -e "$REPO_ROOT/vendor/OpenFrontIO/.git" ]; then
  echo "FATAL: vendor/OpenFrontIO is not initialized; run:" >&2
  echo "  git submodule update --init vendor/OpenFrontIO" >&2
  exit 1
fi

# Cross-check the pin before building: the compiled-in pin, the checkout,
# and docs/pins.md must all agree (the Dockerfile re-checks at build time).
EXPECTED_PIN="$(python3 -c 'import sys; sys.path.insert(0, sys.argv[1]); from openfront_mcp.pins import VENDOR_PIN; print(VENDOR_PIN)' "$REPO_ROOT/src")"
ACTUAL_PIN="$(git -C "$REPO_ROOT/vendor/OpenFrontIO" rev-parse HEAD)"
if [ "$EXPECTED_PIN" != "$ACTUAL_PIN" ]; then
  echo "FATAL: vendor pin mismatch: pins.py=$EXPECTED_PIN checkout=$ACTUAL_PIN" >&2
  exit 1
fi
if ! grep -q -F "$EXPECTED_PIN" "$REPO_ROOT/docs/pins.md"; then
  echo "FATAL: vendor pin $EXPECTED_PIN not recorded in docs/pins.md" >&2
  exit 1
fi

echo ">> building $REF (platform=linux/amd64, vendor=$ACTUAL_PIN)"
if [ "$DRY_RUN" = 1 ]; then
  echo "dry-run: docker buildx build --platform linux/amd64 --load -t \"$REF\" --build-arg \"VENDOR_PIN=$ACTUAL_PIN\" -f \"$DOCKERFILE\" \"$REPO_ROOT\""
  echo "dry-run: docker inspect --format '{{.Architecture}}' \"$REF\""
  exit 0
fi

docker buildx build \
  --platform linux/amd64 \
  --load \
  -t "$REF" \
  --build-arg "VENDOR_PIN=$ACTUAL_PIN" \
  -f "$DOCKERFILE" \
  "$REPO_ROOT"
arch=$(docker inspect --format '{{.Architecture}}' "$REF")
echo "   built $REF (arch=$arch)"
if [ "$arch" != "amd64" ]; then
  echo "FATAL: expected arch amd64, got $arch" >&2
  exit 1
fi

echo "done. local-only image $REF (no-push policy: never pushed to a registry)"
