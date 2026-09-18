# OpenFrontBench Literature Review

Systematic literature review scaffold for OpenFrontBench: a keyless MCP
benchmark harness over the pinned OpenFrontIO RTS engine. This is an RTS
port of the CivBench PMR/RAG methodology from turn boundaries to sim-tick
decision boundaries.

## Purpose

- Ground OpenFrontBench design decisions (paused tick boundaries, PMR/RAG at
  tick granularity, determinism/replay, grid-RLE observation, diary/playbook
  memory) in primary sources.
- Provide the `{proposal}` seed context (`iter_1/proposal_v1.md`) and the 180
  numbered research questions (`iter_3/detailed_research_questions.md`) that
  the T6 batch answers one question per keyless agent session.
- Keep every CI-checkable artefact keyless and docs-only: no LLM calls and
  no network access are required to build or test this directory.

## Layout

```text
docs/lit-review/
├── README.md                        # this file (cycle index)
├── references.bib                   # 13 OpenAlex-verified seed entries
├── latexmkrc                        # minimal bibtex build config
├── iter_1/proposal_v1.md            # seed-context synthesis ({proposal} for T6)
├── iter_2/                          # reserved: first synthesis pass (T7)
├── iter_3/
│   ├── detailed_research_questions.md  # 180 numbered Qs, 30 sections A-AD
│   ├── grouped_research_questions.md   # same 180 Qs grouped into 10 themes
│   ├── *-synthesis.md                  # T7: cline/cursor/kiro syntheses (DRAFT skeletons over Q01–Q180)
│   └── research-prompts/theme-1.md … theme-10.md  # per-theme briefs for T6
├── iter_4/                          # T7: proposal_v4 roadmap + candidate-benchmark report (DRAFT)
├── iter_5/                          # T7: proposal_v5 working proposal (DRAFT, consumes v4 + lit-watch)
└── lit-watch/                       # T8: ongoing intake (ongoing, not seed refs)
    ├── README.md / cron-prompt.md / seen.txt / check_seen.py
    └── daily-files/                 # dated digests (competitive-landscape-YYYY-MM-DD.md)
```

- `iter_1` holds the seed proposal only. Later iterations record syntheses;
  they never rewrite the seed.
- `iter_3` holds the machine-parseable question set. Question lines are
  numbered `1.`–`180.` so the T6 batch regex `^\s*(\d+)\.\s+` parses them.
- `lit-watch/` is the intake queue for post-seed references. Do not add new
  entries to `references.bib` here; that is lit-watch/T8's job.

## How to run the batch (T6 pointer)

The T6 batch runner (to be implemented) reads each numbered question from
`iter_3/detailed_research_questions.md`, injects `iter_1/proposal_v1.md` as
`{proposal}` context plus the matching `research-prompts/theme-N.md` brief,
and runs one keyless docs-grounded agent session per question. Output reports
land under `iter_3/` per the T6 spec. This directory only provides the
inputs; it performs no LLM calls itself.

### Dry-run entry point

```sh
bash docs/lit-review/iter_3/detailed_research_auto/scripts/run.sh --dry-run --start 1 --end 3
```

Keyless only: writes stub reports plus `summary.txt` into the chosen
`--reports-dir` (default `detailed_research_auto/reports/`); `--live`
is refused without `LIVE=1` and a T7 runner.

## Repro policy (keyless docs-only in CI)

- `tests/test_lit_review.py` asserts structure only: file presence, 13+
  bib entries, exactly 180 numbered questions, 30 section headers,
  10 theme groupings, 10 non-empty theme prompts.
- No network, no API keys, no model access. Full `pytest` may fail on
  engine-not-built (pre-existing, unrelated); the lit-review test file must
  pass standalone: `uv run pytest tests/test_lit_review.py -q`.
- Canonical seed sources live outside this directory and are read-only:
  `docs/lit-review-seed.md`, `docs/lit-review-seed.bib`,
  `docs/paper-summary.md`, `docs/openfrontbench-task-spec.md`, `docs/pins.md`.
- Citation ground truth: `references.bib` keys mirror
  `docs/lit-review-seed.bib` verbatim. Verify against OpenAlex; do not rely
  on CrossRef for arXiv-only preprints.
