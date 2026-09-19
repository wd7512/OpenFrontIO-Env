# OpenFrontBench Lit-Review Seed Proposal

**Role:** `{proposal}` context for the keyless batch. One-page synthesis of
`iter_1/seed.md`, `iter_1/civbench-long-horizon-benchmark-tool-mediated-agents-civilization-vi.md`,
`docs/openfrontbench-task-spec.md`, and `docs/pins.md`.

## RTS port of CivBench PMR/RAG to tick boundaries

CivBench (Civ VI, 76 MCP tools, 300+ turn episodes, 29-function narration,
PMR 1–2%, RAG@10 48–66%, 23 runs across 4 model families) is the direct
methodological parent. OpenFrontBench ports its behavioural metrics —
**PMR** = monitoring/non-infra calls and **RAG@K** = (Y + 0.5P)/commitments
over the next K decisions — from turn boundaries to **sim-tick decision
boundaries** in a real-time RTS: pure queries never tick or consume RNG while
`end_decision` advances exactly 50 sim ticks.

## Determinism, replay, grid-RLE

Pinned engine `vendor/OpenFrontIO @ v0.33.14`; fixed seeds plus paired spawn
variants; repeatable manifests (engine/map/config/playbook hashes); full
`trace.jsonl` with accepted-action replay and offline rescore. Observation is
a compact grid-RLE plus narration/telemetry in Python — the RTS analogue of
the CivBench narration layer under information scarcity (the agent only knows
what it explicitly queries).

## Task-spec constraints (binding on every batch report)

uv-only Python; TDD with red/green evidence; isolated per-run OpenCode
config with a versioned five-field diary/playbook; no shell/file/network
tools for the playing agent beyond game MCP; no live evals in CI; missing
key must fail clearly before running; PMR excludes infra and splits
voluntary vs forced monitoring; RAG needs next-ten-decision evidence (no-diary
or zero-commitment runs score N/A, never fabricated); current slice is
`plains-human-smoke` only, so PMR/RAG are honestly `null` until strategic
queries and commitments exist.

## Baselines to position against

CivRealm (FreeCiv+Gymnasium), CivAgent digital player (Unciv+RAG memory),
Vox Deorum (Civ V MCP hybrid, 2,327 games), CivBench V (307 multiplayer
games), BALROG (knowing–doing gap), Vending-Bench (20M-token coherence),
MCPAgentBench (180 tasks/20k tools), SWE-bench (component-isolated contrast),
CICERO (Science 2022 Diplomacy), GameBench/GTBench (short-horizon strategy),
SMACv2 (SC2 micro MARL). Gap claimed: no MCP benchmark over a pinned
open-source RTS with production-tick replay, tick-boundary PMR/RAG, and a
keyless smoke-to-suite pipeline.
