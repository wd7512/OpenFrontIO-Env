# Candidate Benchmark Report (DRAFT dossier skeleton — T7)

**Status:** DRAFT skeleton. No LLM calls, no network. Seeded rows (§1)
transcribe the `docs/lit-review-seed.md` §5 comparison matrix only; every
scoring-rubric cell is an explicit TODO — no fake scores, no invented
citations. Unscored reserve slots (§2) await T8 lit-watch intake and must be
verified via OpenAlex before scoring.

**Rubric columns:** relevance / rigor / fit / effort / score — all TODO
until rescoring criteria are frozen in proposal_v4.

## §1. Seeded dossier (12 works from the seed matrix)

| # | Work | Engine / task | Interface | Long-horizon | PMR-like | RAG-like | OpenFrontBench delta | Relevance | Rigor | Fit | Effort | Score |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | CivBench VI | Civ VI commercial | 76 MCP tools | 300+ turns | yes (PMR) | yes (RAG@10) | port to RTS + tick boundaries | TODO | TODO | TODO | TODO | TODO |
| 02 | CivRealm | FreeCiv | Gymnasium | yes | no | no | MCP + metrics | TODO | TODO | TODO | TODO | TODO |
| 03 | CivAgent / Digital Player | Unciv | LLM sim | yes | no | no | MCP harness + rescore | TODO | TODO | TODO | TODO | TODO |
| 04 | Vox Deorum | Civ V + mod | MCP servers | 2.3k games | no | no | PMR/RAG scoring | TODO | TODO | TODO | TODO | TODO |
| 05 | CivBench V | Civ V multi | victory-prob | 307 games | partial | no | tool-use correctness | TODO | TODO | TODO | TODO | TODO |
| 06 | BALROG | 6 game envs | varied | yes | partial | yes (gap) | RTS + MCP unified | TODO | TODO | TODO | TODO | TODO |
| 07 | Vending-Bench | vending sim | tools | 20M tokens | no | yes (drift) | strategy-game transfer | TODO | TODO | TODO | TODO | TODO |
| 08 | MCPAgentBench | 180 tasks | MCP + distractors | mixed | yes (selection) | yes (efficiency) | game-episode instantiation | TODO | TODO | TODO | TODO | TODO |
| 09 | SWE-bench | GitHub issues | patch | no | no | no | contrast paradigm | TODO | TODO | TODO | TODO | TODO |
| 10 | CICERO (Science 2022) | Diplomacy | dialogue+RL | full games | no | no | RTS + replay + no-assist | TODO | TODO | TODO | TODO | TODO |
| 11 | GameBench / GTBench | board/cards | prompts | short | no | no | live RTS + fog + time | TODO | TODO | TODO | TODO | TODO |
| 12 | SMACv2 | SC2 micro | MARL wrapper | episodes | no | no | full-game MCP + diary | TODO | TODO | TODO | TODO | TODO |

## §2. Reserve slots (unscored — name + verify via lit-watch before scoring)

| # | Work | Engine / task | Interface | Long-horizon | PMR-like | RAG-like | OpenFrontBench delta | Relevance | Rigor | Fit | Effort | Score |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 13 | TODO-CAND-13 — name TBD (lit-watch intake) | TODO | TODO | TODO | TODO | TODO | TODO (verify via OpenAlex before scoring) | TODO | TODO | TODO | TODO | TODO |
| 14 | TODO-CAND-14 — name TBD (lit-watch intake) | TODO | TODO | TODO | TODO | TODO | TODO (verify via OpenAlex before scoring) | TODO | TODO | TODO | TODO | TODO |
| 15 | TODO-CAND-15 — name TBD (lit-watch intake) | TODO | TODO | TODO | TODO | TODO | TODO (verify via OpenAlex before scoring) | TODO | TODO | TODO | TODO | TODO |
| 16 | TODO-CAND-16 — name TBD (lit-watch intake) | TODO | TODO | TODO | TODO | TODO | TODO (verify via OpenAlex before scoring) | TODO | TODO | TODO | TODO | TODO |
| 17 | TODO-CAND-17 — name TBD (lit-watch intake) | TODO | TODO | TODO | TODO | TODO | TODO (verify via OpenAlex before scoring) | TODO | TODO | TODO | TODO | TODO |
| 18 | TODO-CAND-18 — name TBD (lit-watch intake) | TODO | TODO | TODO | TODO | TODO | TODO (verify via OpenAlex before scoring) | TODO | TODO | TODO | TODO | TODO |
| 19 | TODO-CAND-19 — name TBD (lit-watch intake) | TODO | TODO | TODO | TODO | TODO | TODO (verify via OpenAlex before scoring) | TODO | TODO | TODO | TODO | TODO |
| 20 | TODO-CAND-20 — name TBD (lit-watch intake) | TODO | TODO | TODO | TODO | TODO | TODO (verify via OpenAlex before scoring) | TODO | TODO | TODO | TODO | TODO |
| 21 | TODO-CAND-21 — name TBD (lit-watch intake) | TODO | TODO | TODO | TODO | TODO | TODO (verify via OpenAlex before scoring) | TODO | TODO | TODO | TODO | TODO |
| 22 | TODO-CAND-22 — name TBD (lit-watch intake) | TODO | TODO | TODO | TODO | TODO | TODO (verify via OpenAlex before scoring) | TODO | TODO | TODO | TODO | TODO |
| 23 | TODO-CAND-23 — name TBD (lit-watch intake) | TODO | TODO | TODO | TODO | TODO | TODO (verify via OpenAlex before scoring) | TODO | TODO | TODO | TODO | TODO |
| 24 | TODO-CAND-24 — name TBD (lit-watch intake) | TODO | TODO | TODO | TODO | TODO | TODO (verify via OpenAlex before scoring) | TODO | TODO | TODO | TODO | TODO |
| 25 | TODO-CAND-25 — name TBD (lit-watch intake) | TODO | TODO | TODO | TODO | TODO | TODO (verify via OpenAlex before scoring) | TODO | TODO | TODO | TODO | TODO |
| 26 | TODO-CAND-26 — name TBD (lit-watch intake) | TODO | TODO | TODO | TODO | TODO | TODO (verify via OpenAlex before scoring) | TODO | TODO | TODO | TODO | TODO |
| 27 | TODO-CAND-27 — name TBD (lit-watch intake) | TODO | TODO | TODO | TODO | TODO | TODO (verify via OpenAlex before scoring) | TODO | TODO | TODO | TODO | TODO |
| 28 | TODO-CAND-28 — name TBD (lit-watch intake) | TODO | TODO | TODO | TODO | TODO | TODO (verify via OpenAlex before scoring) | TODO | TODO | TODO | TODO | TODO |
| 29 | TODO-CAND-29 — name TBD (lit-watch intake) | TODO | TODO | TODO | TODO | TODO | TODO (verify via OpenAlex before scoring) | TODO | TODO | TODO | TODO | TODO |
| 30 | TODO-CAND-30 — name TBD (lit-watch intake) | TODO | TODO | TODO | TODO | TODO | TODO (verify via OpenAlex before scoring) | TODO | TODO | TODO | TODO | TODO |
| 31 | TODO-CAND-31 — name TBD (lit-watch intake) | TODO | TODO | TODO | TODO | TODO | TODO (verify via OpenAlex before scoring) | TODO | TODO | TODO | TODO | TODO |
| 32 | TODO-CAND-32 — name TBD (lit-watch intake) | TODO | TODO | TODO | TODO | TODO | TODO (verify via OpenAlex before scoring) | TODO | TODO | TODO | TODO | TODO |
| 33 | TODO-CAND-33 — name TBD (lit-watch intake) | TODO | TODO | TODO | TODO | TODO | TODO (verify via OpenAlex before scoring) | TODO | TODO | TODO | TODO | TODO |
| 34 | TODO-CAND-34 — name TBD (lit-watch intake) | TODO | TODO | TODO | TODO | TODO | TODO (verify via OpenAlex before scoring) | TODO | TODO | TODO | TODO | TODO |
| 35 | TODO-CAND-35 — name TBD (lit-watch intake) | TODO | TODO | TODO | TODO | TODO | TODO (verify via OpenAlex before scoring) | TODO | TODO | TODO | TODO | TODO |
| 36 | TODO-CAND-36 — name TBD (lit-watch intake) | TODO | TODO | TODO | TODO | TODO | TODO (verify via OpenAlex before scoring) | TODO | TODO | TODO | TODO | TODO |
| 37 | TODO-CAND-37 — name TBD (lit-watch intake) | TODO | TODO | TODO | TODO | TODO | TODO (verify via OpenAlex before scoring) | TODO | TODO | TODO | TODO | TODO |
| 38 | TODO-CAND-38 — name TBD (lit-watch intake) | TODO | TODO | TODO | TODO | TODO | TODO (verify via OpenAlex before scoring) | TODO | TODO | TODO | TODO | TODO |
| 39 | TODO-CAND-39 — name TBD (lit-watch intake) | TODO | TODO | TODO | TODO | TODO | TODO (verify via OpenAlex before scoring) | TODO | TODO | TODO | TODO | TODO |
| 40 | TODO-CAND-40 — name TBD (lit-watch intake) | TODO | TODO | TODO | TODO | TODO | TODO (verify via OpenAlex before scoring) | TODO | TODO | TODO | TODO | TODO |
| 41 | TODO-CAND-41 — name TBD (lit-watch intake) | TODO | TODO | TODO | TODO | TODO | TODO (verify via OpenAlex before scoring) | TODO | TODO | TODO | TODO | TODO |
| 42 | TODO-CAND-42 — name TBD (lit-watch intake) | TODO | TODO | TODO | TODO | TODO | TODO (verify via OpenAlex before scoring) | TODO | TODO | TODO | TODO | TODO |

## Scoring notes

- Do not score a reserve slot until its reference is verified (OpenAlex HIT
  + venue confirmation); arXiv-only preprints must not rely on CrossRef
  (see seed §8 provenance lesson).
- Rescoring is frozen against proposal_v4 RQ thresholds; record the
  manifest (report version + date) with every score change.
