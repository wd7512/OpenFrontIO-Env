# Docker runbook (reproducible openfront-env base)

## Prereqs

- Docker with the buildx plugin: `docker buildx version`.
- A checkout with the engine submodule initialized:
  `git submodule update --init vendor/OpenFrontIO`.
- The wrapper `scripts/build-openfront.sh` (builds `openfront-env:<tag>`,
  local daemon only).

## Build

```bash
scripts/build-openfront.sh
scripts/build-openfront.sh --tag mytest
scripts/build-openfront.sh --dry-run   # print the docker commands only
```

The tag defaults to the git short SHA, else `local`. The script first
cross-checks the vendor pin (`src/openfront_mcp/pins.py` vs the
`vendor/OpenFrontIO` checkout vs `docs/pins.md`, all must agree), then runs
`docker buildx build --platform linux/amd64 --load`, and finally asserts
`docker inspect {{.Architecture}}` reports `amd64`, failing otherwise.

## Smoke (keyless, inside the container)

```bash
docker run --rm openfront-env:local uv run --no-sync python -m openfront_mcp.benchmark --config examples/smoke.json --output /tmp/smoke-out
```

`/tmp/smoke-out` is fresh on every container start, which the CLI requires
(it refuses to overwrite an existing directory). Exit 0 plus
`result.json` / `trace.jsonl` / `manifest.json` means the engine bundle, map
assets and vendor pin all verified. To keep artifacts, mount a host dir and
write under a fresh subdir:

```bash
mkdir -p .smoke && docker run --rm -v "$PWD/.smoke:/out" openfront-env:local \
  uv run --no-sync python -m openfront_mcp.benchmark --config examples/smoke.json --output /out/run1
```

## Arch notes

- Dev hosts here are arm64 (Apple silicon); the image targets `linux/amd64`,
  so local builds run under QEMU emulation via buildx and are slower than
  native. Prefer a native amd64 builder for release images and record the
  resulting digest in the pinned-images allowlist.
- The Dockerfile pins `python:3.12`, `uv==0.11.11` and Node major 22;
  base-image patch versions float until pinned by digest (T2 follow-up).

## No-push policy

Tags are local-only (`openfront-env:<sha-or-local>`). The build script has
no `--push` path and refuses push-related arguments; never add one.
Promotion to a registry is a separate, deliberate step (T2).

## Troubleshooting

- `engine bundle missing: engine/dist/worker.mjs` (build or manifest
  failure): the engine was not built. On the host, run
  `cd engine && npm ci && npm run build && cd ..`. The Dockerfile fails the
  build if `npm run build` did not produce the bundle.
- `vendor pin mismatch: expected ..., actual ...`: the `vendor/OpenFrontIO`
  checkout drifted from `docs/pins.md`. Re-pin with
  `git submodule update --init vendor/OpenFrontIO` (detached head at the
  recorded pin) and rebuild.
- `cannot verify vendor pin (git unavailable)`: the runtime probe needs git
  metadata. Images built by the script carry the verified build-time SHA as
  a detached HEAD in `vendor/OpenFrontIO`, so this only appears for
  hand-built images or host runs outside git; rebuild via the script.
- Exec-format errors or wrong `arch=` at run time: an arm64 image was loaded
  or the arch guard was skipped. Rebuild with the script and confirm with
  `docker inspect --format '{{.Architecture}}' openfront-env:<tag>`.
