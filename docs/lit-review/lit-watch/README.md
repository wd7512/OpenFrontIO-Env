# OpenFrontBench lit-watch (ongoing intake)

Daily intake queue for post-seed references. Seed refs stay frozen in
`docs/lit-review/references.bib` (13 OpenAlex-verified works); everything new
lands here first and is promoted only through this pipeline.

## Pipeline

1. **Discovery swarm** — keyless docs-grounded sweep from `docs/lit-review`
   for harness / MCP-agent / RTS-eval work from roughly the last 7 days.
   Candidates only: ID + title + one-line relevance.
2. **arXiv `id_list` verify** — every reported arXiv ID is resolved via the
   arXiv API (`id_list` query). Title must match; withdrawn or unresolvable
   IDs are discarded. Zero fabricated IDs.
3. **Dedup against `seen.txt`** — any identifier already listed is skipped
   and never re-reported. New identifiers are appended (sorted, one per
   line) only after verification.
4. **Tier1 / Tier2 classify** — Tier1 = harness / MCP-agent / RTS-eval work
   with a verifiable arXiv ID or DOI; Tier2 = adjacent work (coherence,
   partial evaluation, game benchmarks). See `cron-prompt.md` STEP 5.
5. **Scoped commit only** — `git add docs/lit-review/lit-watch/` and nothing
   else. Never `-A`, never other paths.
   Commit message: `lit-watch: update seen-list (YYYY-MM-DD)`.
6. **Digest** — tiered daily file under `daily-files/` plus the
   `Harness lit watch — YYYY-MM-DD` delivery block (see `cron-prompt.md`
   STEP 7). Consumed by `iter_5/proposal_v5.md`.

## Recreate instructions

This directory is files + tooling only. No cron is configured in this repo
and no network or API keys are required to build or test it.

To activate a daily run (outside CI — see keyless-CI note):

1. Create a scheduler job (cron / Hermes / CI-scheduled workflow) with
   `prompt` = the full verbatim contents of `cron-prompt.md`.
2. Give the job repo-root workdir, file + terminal + web toolsets, and
   push access to branch `overhaul/lit-review` (or `main` once merged).
3. The job follows STEPS 1–7 in `cron-prompt.md`: discover → verify →
   dedup → classify → scoped commit → digest.
4. Verify the run: `seen.txt` still contains all baseline IDs, new IDs are
   appended sorted, and the commit touches only `docs/lit-review/lit-watch/`.

## Idempotency rule

Re-running any step is idempotent: re-discovery of an already-seen ID is a
no-op, re-appending never duplicates or drops baseline IDs, and re-committing
with no new IDs produces no commit. `check_seen.py` enforces this
(`NEW` vs `DUPLICATE`); CI and the daily job both rely on it.

## Keyless-CI note

CI is keyless and docs-only: `tests/test_lit_watch.py` checks structure
(file presence, sorted `seen.txt`, Tier headers, scoped-add rule) with no
network, no API keys, and no model access. The live cron (network arXiv
verify, swarm discovery, push) always runs outside CI.

## Files

- `seen.txt` — dedup ledger, one identifier per line (arXiv IDs + DOIs).
- `cron-prompt.md` — verbatim executable daily prompt (STEPS 1–7).
- `check_seen.py` — stdlib dedup checker (`--seen --check`).
- `daily-files/` — dated digests (`competitive-landscape-YYYY-MM-DD.md`).
