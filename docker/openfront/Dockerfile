# Reproducible base image for OpenFrontIO-Env (keyless smoke harness).
#
# Pattern ported from custom-harbor (docker/opencode/Dockerfile plus
# scripts/build-amd64.sh): buildx platform build, pinned tooling,
# local-only tags, no secrets baked in.
#
# The layout mirrors the repo root: the harness resolves paths from its own
# location (src/openfront_mcp/paths.py), so WORKDIR /app must hold
# pyproject.toml, src/, engine/, vendor/ and examples/ side by side.
#
# Build with scripts/build-openfront.sh (local tags only, never pushed).

FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

# Pinned toolchain: exact uv, Node major 22 (LTS) via NodeSource, Python
# minor pinned by the base image tag.
ARG UV_VERSION=0.11.11
ARG NODE_MAJOR=22
# Resolved by scripts/build-openfront.sh from the build context and recorded
# as image metadata (mirrors the custom-harbor digest-recording practice).
ARG VENDOR_PIN=unknown

LABEL org.opencontainers.image.revision="${VENDOR_PIN}"

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl git \
    && curl -fsSL https://deb.nodesource.com/setup_${NODE_MAJOR}.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && node --version \
    && npm --version \
    && test "$(node -p "process.versions.node.split('.')[0]")" = "$NODE_MAJOR" \
    && pip install --no-cache-dir "uv==${UV_VERSION}" \
    && uv --version

WORKDIR /app

# Python dependencies first for layer caching. README ships because
# pyproject.toml declares it; src/ ships because `uv sync` installs the
# locked project itself, not just its dependencies.
COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/
RUN uv sync --frozen --dev

# Engine bundle: deterministic install, then build the worker from the
# vendored core. The submodule must be initialized in the build context:
# `git submodule update --init vendor/OpenFrontIO` (see docs/pins.md).
COPY engine/package.json engine/package-lock.json ./engine/
RUN cd engine && npm ci
COPY engine/ ./engine/
COPY vendor/ ./vendor/
RUN cd engine && npm run build

# Episode input and pin record (read-only data for the smoke CLI).
COPY examples/ ./examples/
COPY docs/pins.md ./docs/pins.md

# Build-time verification; any failure stops the build:
# 1. the engine bundle was produced,
# 2. the compiled-in vendor pin (src/openfront_mcp/pins.py) is recorded in
#    docs/pins.md,
# 3. no secret files leaked into the image (only the explicit COPYs above
#    run, so .env files can never arrive here; this guard says so plainly).
# The vendor checkout ships without .git history, but the runtime manifest
# probe shells out to `git rev-parse HEAD` inside vendor/OpenFrontIO. When
# no git metadata arrived with the context, record the verified pin as a
# detached HEAD so the probe sees the exact built sources. The value is
# cross-checked in step 2 and re-checked against the context by
# scripts/build-openfront.sh before the build starts.
RUN test -f engine/dist/worker.mjs \
    && PIN="$(uv run --no-sync python -c "from openfront_mcp.pins import VENDOR_PIN; print(VENDOR_PIN)")" \
    && grep -q -F "$PIN" docs/pins.md \
    && echo "vendor pin OK: $PIN" \
    && (test -e vendor/OpenFrontIO/.git || (git init -q vendor/OpenFrontIO && echo "$PIN" > vendor/OpenFrontIO/.git/HEAD)) \
    && test "$(git -C vendor/OpenFrontIO rev-parse HEAD)" = "$PIN" \
    && test ! -e .env \
    && test ! -e .env.local

# No EXPOSE: the harness speaks MCP over stdio and serves no ports.
# Boring default: show the keyless smoke CLI help (exits 0, needs nothing).
CMD ["uv", "run", "--no-sync", "python", "-m", "openfront_mcp.benchmark", "--help"]
