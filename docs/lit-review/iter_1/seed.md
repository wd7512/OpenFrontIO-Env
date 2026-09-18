# Lit Review Seed — OpenFrontBench

*Compiled 2026-09-18. Scope: `OpenFrontIO-Env` repo + the CivBench paper
note (`civbench-long-horizon-benchmark-tool-mediated-agents-civilization-vi.md`),
`docs/openfrontbench-task-spec.md`, `docs/pins.md`. All entries verified via
research subagent MCPs (OpenAlex HIT; CrossRef HIT only for published venues;
PubMed out of scope). See `seed.bib` for citations.*

## 0. What we are building (repo grounding)

**OpenFrontBench** is a keyless MCP benchmark harness over the pinned real
OpenFrontIO engine (`vendor/OpenFrontIO` @ `v0.33.14`, see `docs/pins.md`).
Stack: Python MCP server (FastMCP, `src/openfront_mcp/server.py`), persistent
Node/TS JSONL worker over production core (`engine/`), narration + telemetry
in Python (`narrate.py`, `metrics.py`, `diary.py`).

Design constraints from `docs/openfrontbench-task-spec.md`:

- Paused decision boundaries: queries do not tick or consume RNG;
  `end_decision` advances exactly 50 sim ticks.
- Information scarcity: agent only knows what it explicitly queries.
- Fixed seeds + paired spawn variants, repeatable manifests
  (engine/map/config/playbook hashes), full `trace.jsonl` + offline rescore.
- Five-field diary + versioned playbook; isolated per-run OpenCode config;
  no shell/file/network tools for the playing agent beyond game MCP.
- Behavioural metrics ported from CivBench (`src/openfront_mcp/metrics.py`,
  `evals/metrics.py`): **PMR** = monitoring/non-infra calls,
  **RAG@K** = (Y + 0.5P)/commitments over next-K decisions.
- Current slice (`README.md`): `plains-human-smoke` only — one human, no
  opponents, no victory claims; PMR/RAG `null` in smoke (no strategic-query
  or commitment events yet).

## 1. Anchor — CivBench (Civ VI, MCP, PMR/RAG)

**CivBench** [@andrews2026civbench] is the direct methodological parent:
76 MCP tools over live Civ VI via FireTuner, 300+ turn episodes, narration
layer (29 functions), PMR + RAG@10, 23 runs across 4 model families.
Findings we inherit: sensorium effect (PMR 1–2%, 7/20 detectable defeats
unqueried), reflection–action gap (RAG@10 48–66%), outcome measures compress
variance. OpenFrontBench ports PMR/RAG to a real-time (not turn-based) RTS
with sim-tick decision boundaries instead of turn boundaries.

## 2. Civ-game environments (prior art, different engines)

- **CivRealm** [@qi2024civrealm] (ICLR 2024 Spotlight, FreeCiv + Gymnasium).
  Imperfect-info general-sum games, changing player counts, diplomacy + NL
  communication. Prior art for Civ-as-agent-testbed; no MCP, no PMR/RAG.
- **CivAgent / Digital Player** [@wang2025digitalplayer] (Unciv, FuxiAILab).
  LLM digital player with diplomacy skills, RAG memory, lookahead simulator,
  human-likeness focus. Parallel tool-mediated idea; no MCP harness, no
  monitoring/execution metrics.
- **Vox Deorum** [@chen2025voxdeorum] (Civ V + Vox Populi, 2,327 games).
  Hybrid LLM+X: LLM macro-strategy + algorithmic tactics. Closest
  architecturally — actually exposes game state via MCP servers — but
  delegation model, not turn-level PMR/RAG scoring.
- **CivBench (Civ V)** [@chen2026civbenchV] (307 multiplayer Civ V games,
  7 LLMs). Turn-level victory-probability estimation / progress-based eval.
  Shares long-horizon spirit; no MCP tool integration, decision-quality
  focus rather than tool-use correctness.

Takeaway: the Civ community splits by engine access (FreeCiv/Unciv/Civ V-mod
vs commercial Civ VI via FireTuner). OpenFrontIO gives us a third path:
pinned open-source RTS core with production-tick fidelity.

## 3. Long-horizon / tool-mediated evals (methods we borrow/contrast)

- **BALROG** [@paglieri2025balrog] (ICLR 2025). Knowing–doing gap across
  6 game envs; trajectory milestones. Direct ancestor of RAG: models state
  plans they do not execute.
- **Vending-Bench** [@backlund2025vendingbench] (20M+ token runs). Coherence
  breakdowns are behavioural (goal-drift, meltdown loops), not context-limit.
  Justifies RAG as behavioural, not architectural, measure.
- **MCPAgentBench** [@liu2025mcpagentbench] (180 tasks / 20k tools, distractors,
  sandbox, completion + efficiency). Closest methods sibling for keyless MCP
  harness design: tool-selection discrimination, distractor handling, efficiency
  scoring → maps to our PMR (proactive selection) + rescore pipeline.
- **SWE-bench** [@jimenez2024swebench] (ICLR 2024). Component-isolated
  patch-eval contrast: single-turn code fix vs our multi-turn tool-mediated
  episodes. Its held-out-test scoring is the ancestor of our offline rescore.

## 4. Strategy / multi-agent game AI (capability context)

- **CICERO** [@bakhtin2022cicero] (*Science* 2022). Human-level Diplomacy via
  LM dialogue + planning/RL. Canonical proof that LM + search negotiates and
  plans under cooperation/competition; we extend to RTS with deterministic
  replay and no hidden assistance.
- **GameBench** [@costarelli2024gamebench] (9 games, strategic-reasoning axes)
  and **GTBench** [@duan2024gtbench] (10 game-theoretic tasks). Both cover
  board/card/classical games, not live RTS with fog-of-war + continuous time.
  OpenFrontBench fills the RTS + real-engine-replay gap.
- **SMACv2** [@ellis2023smacv2] (NeurIPS 2023, StarCraft II micro). Standard
  cooperative MARL benchmark; scripted wrapper, not full-game tool-mediated
  play. Our contrast: full-game episodes, diary/playbook, paused boundaries.

## 5. Comparison matrix

| Work | Engine / task | Interface | Long-horizon | PMR-like | RAG-like | OpenFrontBench delta |
|---|---|---|---|---|---|---|
| CivBench VI | Civ VI commercial | 76 MCP tools | 300+ turns | yes (PMR) | yes (RAG@10) | port to RTS + tick boundaries |
| CivRealm | FreeCiv | Gymnasium | yes | no | no | MCP + metrics |
| CivAgent | Unciv | LLM sim | yes | no | no | MCP harness + rescore |
| Vox Deorum | Civ V + mod | MCP servers | 2.3k games | no | no | PMR/RAG scoring |
| CivBench V | Civ V multi | victory-prob | 307 games | partial | no | tool-use correctness |
| BALROG | 6 game envs | varied | yes | partial | yes (gap) | RTS + MCP unified |
| Vending-Bench | vending sim | tools | 20M tokens | no | yes (drift) | strategy-game transfer |
| MCPAgentBench | 180 tasks | MCP + distractors | mixed | yes (selection) | yes (efficiency) | game-episode instantiation |
| SWE-bench | GitHub issues | patch | no | no | no | contrast paradigm |
| CICERO | Diplomacy | dialogue+RL | full games | no | no | RTS + replay + no-assist |
| GameBench/GTBench | board/cards | prompts | short | no | no | live RTS + fog + time |
| SMACv2 | SC2 micro | MARL wrapper | episodes | no | no | full-game MCP + diary |

## 6. Gaps → OpenFrontBench contributions (seed claims)

1. No MCP benchmark over a pinned open-source RTS with production-tick
   replay + manifest verification.
2. No PMR/RAG instantiation for RTS decision-tick (vs turn) boundaries with
   pure-query vs advancing-action separation.
3. No keyless smoke-to-suite pipeline (scripted controller → isolated LLM
   runs → offline PMR/RAG rescore) with honest coverage labels.
4. No diary/playbook + commitment-tracking ablation path for RTS agents.

## 7. Next seeds (not yet verified)

- OpenFrontIO upstream docs / map-gen / combat formulas (vendor pin only).
- FireTuner / Civ VI modding constraints vs OpenFront worker comparison.
- Commitment-labelling reliability (Claude Haiku κ=0.879 pipeline in CivBench)
  adapted to free-text diary validation (`diary.py`).
- Cry Havoc-style stress scenario for RTS (Immortal-equivalent pressure).

## 8. MCP provenance

OpenAlex HIT for all 13 (including `W7207781962` for CivBench VI).
CrossRef HIT only for `CICERO` (10.1126/science.ade9097) and `SMACv2`
proceedings; MISS for all arXiv-only preprints (harvest lag + publisher-DOI
bias). PubMed MISS throughout (biomedical scope). Lesson: seed from OpenAlex,
confirm venues via proceedings/OpenReview, do not rely on CrossRef for
preprints.

*All summaries cross-checked against the CivBench paper note §6; tribunal:
CivBench VI is the only entry with PMR/RAG ground truth in-repo.*
