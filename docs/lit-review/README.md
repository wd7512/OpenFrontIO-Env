# OpenFrontBench Literature Review

First-pass literature review for OpenFrontBench: a keyless MCP benchmark
harness over the pinned OpenFrontIO RTS engine. This is an RTS port of the
CivBench PMR/RAG methodology from turn boundaries to sim-tick decision
boundaries.

Honest status: exactly one research pass exists (`iter_1/`). No batch has
been run, no synthesis written, no proposal consolidated beyond the seed.
Any future research process will define its own structure; nothing here
implies iterations that have not happened.

## Purpose

- Ground OpenFrontBench design decisions (paused tick boundaries, PMR/RAG at
  tick granularity, determinism/replay, grid-RLE observation, diary/playbook
  memory) in primary sources.
- Provide the `{proposal}` seed context (`iter_1/proposal.md`) and the
  numbered research questions (`iter_1/research-questions.md`) that a future
  batch can answer one question per keyless agent session.
- Keep every CI-checkable artefact keyless and docs-only: no LLM calls and
  no network access are required to build or test this directory.

## Layout

```text
docs/lit-review/
├── README.md                        # this file
├── references.bib                   # 13 OpenAlex-verified seed entries (mirrors iter_1/seed.bib)
├── latexmkrc                        # minimal bibtex build config
├── iter_1/                          # the single existing research pass
│   ├── proposal.md                  # seed-context synthesis ({proposal} for the batch)
│   ├── seed.md                      # grounded starting point: matrix, gaps, contributions
│   ├── seed.bib                     # provenance bib (references.bib mirrors it)
│   ├── civbench-*.md                # paper note: CivBench, the methodological parent
│   ├── research-questions.md        # numbered Qs in sections
│   └── batch/                       # reusable batch tooling (dry-run only)
│       ├── scripts/run.py           # orchestrator: parse, prompt, stub reports
│       ├── scripts/run.sh           # CLI wrapper (always --dry-run; --live refused)
│       ├── scripts/extract_questions.sh  # standalone N|question parser
│       ├── sandbox/                 # model + MCP lockfile and agent contract
│       └── reports/                 # empty: reports land here when a batch runs
└── lit-watch/                       # ongoing intake (not an iteration)
    ├── README.md / cron-prompt.md / seen.txt / check_seen.py
    └── daily-files/                 # empty: dated digests land here
```

- `iter_1` holds everything from the first pass: raw materials (`seed.*`,
  paper note), the proposal, the question set, and the batch tooling. A
  future process may add `iter_2/`; it must never rewrite `iter_1`.
- Question lines are numbered (`1.`, `2.`, …) so the batch regex
  `^\s*(\d+)\.\s+` parses them.
- `lit-watch/` is the intake queue for post-seed references. Do not add new
  entries to `references.bib`; that is lit-watch's job.

## How to run the batch

The batch runner reads each numbered question from
`iter_1/research-questions.md`, injects `iter_1/proposal.md` as `{proposal}`
context, and prepares one stub report per question. This directory performs
no LLM calls itself.

### Dry-run entry point

```sh
bash docs/lit-review/iter_1/batch/scripts/run.sh --dry-run --start 1 --end 3
```

Keyless only: writes stub reports plus `summary.txt` into the chosen
`--reports-dir` (default `batch/reports/`); `--live` is refused without
`LIVE=1` and a future live runner.

## Repro policy (keyless docs-only in CI)

- `tests/test_lit_review.py` asserts structure only: file presence, 13+
  bib entries, numbered questions in sequence, section headers, seed
  files in `iter_1/`, and no later iterations.
- No network, no API keys, no model access. Full `pytest` may fail on
  engine-not-built (pre-existing, unrelated); the lit-review test files must
  pass standalone.
- Canonical seed sources: `iter_1/seed.md`, `iter_1/seed.bib`, the CivBench
  paper note, `docs/openfrontbench-task-spec.md`, `docs/pins.md`.
- Citation ground truth: `references.bib` keys mirror `iter_1/seed.bib`
  verbatim. Verify against OpenAlex; do not rely on CrossRef for arXiv-only
  preprints.
