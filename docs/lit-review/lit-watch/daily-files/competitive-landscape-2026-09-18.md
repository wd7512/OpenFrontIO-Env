# Harness lit watch — 2026-09-18

> **SAMPLE / DRAFT** — skeleton digest for T8 tooling only. No live discovery
> was run; rows below are TODO placeholders. No papers beyond the 13 seed
> works are claimed. Baseline seed works (already in `seen.txt`, never
> re-reported): CivBench 2026 (2609.02459), CivRealm (2401.10568),
> Digital Player (2502.20807), Vox Deorum (2512.18564), CivBench-V
> (2604.07733), BALROG (2411.13543), Vending-Bench (2502.15840),
> MCPAgentBench (2512.24565), SWE-bench (2310.06770), Cicero
> (10.1126/science.ade9097), GameBench (2406.06613), GTBench (2402.12348),
> SMACv2 (2212.07489).

## Tier 1 — harness / MCP-agent / RTS-eval (verifiable arXiv/DOI only)

| Title | ID (arXiv/DOI) | Date | Relevance to OpenFrontBench | Verified |
|---|---|---|---|---|
| TODO: first Tier1 candidate (e.g. MCP tool-use benchmark) | TODO: arXiv ID | TODO | TODO: one-line relevance (tick-boundary / replay / MCP tools) | TODO: `id_list` title match |
| TODO: second Tier1 candidate (e.g. RTS-eval paper) | TODO: DOI | TODO | TODO: one-line relevance | TODO |

## Tier 2 — adjacent (coherence / partial eval / game benchmarks)

| Title | ID (arXiv/DOI) | Date | Brief | Verified |
|---|---|---|---|---|
| TODO: adjacent candidate (e.g. long-horizon coherence) | TODO | TODO | TODO: one-line brief | TODO |
| TODO: adjacent candidate (e.g. progress-based eval) | TODO | TODO | TODO | TODO |

## Verification checklist

- [ ] TODO: every reported arXiv ID resolved via arXiv API `id_list`; title matches.
- [ ] TODO: every reported DOI resolves (https://doi.org/); drop unresolvable.
- [ ] TODO: withdrawn entries discarded.
- [ ] TODO: `uv run python docs/lit-review/lit-watch/check_seen.py --seen docs/lit-review/lit-watch/seen.txt --check docs/lit-review/lit-watch/daily-files/competitive-landscape-2026-09-18.md` reports only NEW IDs (exit 1) or no NEW IDs (exit 0, nothing to file).

## Seen-append note

- TODO: append newly verified IDs to `docs/lit-review/lit-watch/seen.txt` (sorted, deduped, one per line); verify baseline IDs intact.
- TODO: scoped commit only: `git add docs/lit-review/lit-watch/` then `git commit -m "lit-watch: update seen-list (2026-09-18)"`. Never `-A`, never other paths.
- Also filed to seen-list (not delivered): TODO count — TODO IDs.

## Ecosystem one-liners

- Harness/MCP release: TODO (or "none new").
- Benchmark-invalidation news: TODO (or "none new").
- Competitor RTS/long-horizon eval news: TODO (or "none new").
