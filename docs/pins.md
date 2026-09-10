# Pinned dependencies

## upstream-openfrontio

- Path: vendor/OpenFrontIO
- Remote: https://github.com/openfrontio/OpenFrontIO.git
- Pin: v0.33.14 (577819ba0e1e13ecdbc8dede2ba33de542c88a67, 2026-09-04)
- Mode: detached head, do not track upstream HEAD
- Scope: MCP server builds against src/core only; client/server untouched
- Reason: v0.33.14 is the tick-grid validated version (36-cell grid, 3 versions x 4 cadences)
- Update policy: bump tag deliberately, re-run harness, record new hash here
