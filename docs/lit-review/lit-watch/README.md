# OpenFrontBench lit-watch (ongoing intake)

Daily intake queue for post-seed references. Seed refs stay frozen in
`docs/lit-review/references.bib` (13 OpenAlex-verified works); everything new
lands here first and is promoted only through this pipeline.

## Pipeline

1. **Discover** — sweep recent work relevant to the study (see
   `cron-prompt.md`). Candidates only: ID + title + one-line relevance.
2. **Verify** — every reported arXiv ID is resolved via the arXiv API.
   Title must match; withdrawn or unresolvable IDs are discarded.
   Zero fabricated IDs.
3. **Dedup against `seen.txt`** — any identifier already listed is skipped
   and never re-reported. New identifiers are appended (sorted, one per
   line) only after verification.
4. **Record + scoped commit only** — `git add docs/lit-review/lit-watch/`
   and nothing else. Never `-A`, never other paths.
5. **Digest** — dated file under `daily-files/` (see `cron-prompt.md`).

## Recreate instructions

This directory is files + tooling only. No cron is configured in this repo
and no network or API keys are required to build or test it.

To activate a daily run (outside CI — see keyless-CI note):

1. Create a scheduler job with `prompt` = the full verbatim contents of
   `cron-prompt.md`.
2. Give the job repo-root workdir, file + terminal + web toolsets, and
   `push access to the branch the job runs on.
3. The job follows `cron-prompt.md`: discover → verify → dedup → record → digest.
4. Verify the run: `seen.txt` still contains all baseline IDs, new IDs are
   appended sorted, and the commit touches only `docs/lit-review/lit-watch/`.

## Idempotency rule

Re-running any step is idempotent: re-discovery of an already-seen ID is a
no-op, re-appending never duplicates or drops baseline IDs, and re-committing
with no new IDs produces no commit. `check_seen.py` enforces this
(`NEW` vs `DUPLICATE`); CI and the daily job both rely on it.

## Keyless-CI note

CI is keyless and docs-only: `tests/test_lit_watch.py` checks structure
(file presence, sorted `seen.txt`, scoped-add rule) with no
network, no API keys, and no model access. The live intake job (network
verify, discovery, push) always runs outside CI.

## Files

- `seen.txt` — dedup ledger, one identifier per line (arXiv IDs + DOIs).
- `cron-prompt.md` — verbatim executable intake prompt.
- `check_seen.py` — stdlib dedup checker (`--seen --check`).
- `daily-files/` — dated digests (`YYYY-MM-DD.md`).
