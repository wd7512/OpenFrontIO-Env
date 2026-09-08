# Paper Summary: CivBench — A Long-Horizon Benchmark for Tool-Mediated Agents in Civilization VI

**arXiv:** [2609.02459](https://arxiv.org/abs/2609.02459) (cs.AI) | **Submitted:** 2 Sep 2026 | **Venue:** NeurIPS 2026 E&D Track
**Authors:** Andrews\*, Wilkinson\*, Heagerty, Coppock, Foerster, Costa (Oxford, Google DeepMind, UK AISI, Imperial)
**Code:** [github.com/lmwilki/civ6-mcp](https://github.com/lmwilki/civ6-mcp) (MIT) | **Web:** [civ6-mcp.lwilko.com/civbench](https://civ6-mcp.lwilko.com/civbench)

---

## 1. Contribution & Benchmark Design

CivBench is an **open-source benchmark** evaluating LLM agents in long-horizon, tool-mediated environments via the **Model Context Protocol (MCP)**. It connects agents to a live game of **Civilization VI** (commercial 2016+ title, not FreeCiv), where:

- A single episode spans **300+ turns** producing **thousands of tool calls** over a large action space
- **76 MCP tools** cover state queries, unit control, city management, diplomacy, research, governance, religion, trade, and game lifecycle
- A **narration layer** (29 functions) converts visual game state into structured text
- Agents interact via tool calls — **not** pixels or custom Gymnasium APIs

**Core design philosophy:** Separate *information availability* from *information retrieval*. All non-local state must be explicitly queried, enabling CivBench to distinguish "unavailable" from "available but not retrieved" — making attention allocation measurable from interaction traces.

**Four contributions:**
1. **Benchmark environment** — MCP benchmark for full-game Civ VI with 76 tools, fixed scenarios, structured logs
2. **Narration protocol** — Structured interface preserving controlled observability
3. **Behavioural metrics:**
   - **PMR (Proactive Monitoring Rate):** `strategic_monitoring_calls / non_infrastructure_calls`
   - **RAG@K (Reflection–Action Gap):** `(Y + 0.5P) / total_commitments` over K=10 turns
4. **Empirical characterisation** — 23 admissible runs across 4 model families

**Scenarios:** Ground Control (Prince, baseline), Snowflake (King, military), Cry Havoc (Immortal, excluded from results).

---

## 2. Agent Architecture Tested

**Model families (23 admissible runs):**

| Model | Runs | Access |
|-------|------|--------|
| Claude Opus 4.6 (Anthropic) | 6–8 | Anthropic API |
| Gemini 3.1 Pro (Google) | 6–8 | Google AI |
| GPT-5.4 (OpenAI) | 6–8 | OpenAI API |
| Kimi-K2.5 (Moonshot AI) | 1 | Azure AI Foundry (2026-04-18) |

**Protocol:** Single LLM agent vs Civ VI built-in AI opponents. All models share the same versioned playbook (turn structure, checkpoints, five-field diary: tactical/strategic/tooling/planning/hypothesis). Agent decides which tools to call and when; a typical turn uses 5–15 tool calls.

**MCP architecture:**
```
LLM Agent → MCP Tools (76, stdio JSON-RPC) → CivBench MCP Server → FireTuner (TCP) → Civ VI
   ↑                                                                              │
   └────────── Structured text via Narration Layer ◄──────────────────────────────┘
```
The server translates calls to Civ VI and returns structured observations through the narration layer.

---

## 3. Companion Repository: civ6-mcp

**Repo:** [github.com/lmwilki/civ6-mcp](https://github.com/lmwilki/civ6-mcp) (MIT, Liam Wilkinson 2026)

**Architecture:**
```
Any MCP Client → stdio (JSON-RPC) → CivBench MCP Server (Python) → TCP :4318 → FireTuner → Civ VI
       ↑                                                                     │
       └─────── Structured text via Narration Layer (29 functions) ◄─────────┘
```

**76 MCP tools** across 13 categories: Units (list/move/attack/fortify/found/build/promote/upgrade), Cities (inspect/production/purchase/focus), Map (terrain/resources/fog/settle advice), Research (tech/civic trees), Diplomacy (relationships/modifiers/alliances), Trade (routes/destinations), Government (policy cards/eras), Governors (appoint/assign/promote), Religion (pantheons/beliefs/spread), Great People (recruit/patronize/reject), World Congress (resolutions/favor), Victory (all conditions), Game lifecycle (save/load/launch/restart/kill).

**Key repo contents:**
- `evals/` — CivBench evaluation harness with 3 scenario saves (Ground Control, Snowflake, Cry Havoc)
- `docs/devlog/` — 12 game playthroughs (Poland, Rome, Macedonia, Byzantium, India, Portugal, Scythia, England, Mali, Korea)
- `docs/paper/` — scenario specs
- `docs/agent-essays/` — "The Hallucination of Competence" and agent-vs-agent analysis
- `web/` — Full Next.js dashboard (Convex backend) with map visualization, leaderboards, ELO ratings, diary viewer
- `AGENTS.md` — Detailed playbook (turn loop, diary protocol, strategic checkpoints)

**Playbook (from AGENTS.md):**
- Turn loop: overview → units → map → move → cities → districts → production → strategic checkpoints → end_turn
- Five-field diary (required, non-empty): tactical, strategic, tooling, planning, hypothesis
- Empire warnings auto-run on end_turn (loyalty, trade routes, gold, military, scoreboard)
- Information scarcity principle: "You only know what you explicitly query"

**Client configs included:** Claude Code (`.mcp.json`), Claude Desktop, Codex (`.codex/config.toml`), Gemini CLI (`.gemini/settings.json`), generic stdio

---

## 4. Key Results & Findings

**Aggregate outcomes are insufficient.** Only 3 victories in 23 runs (all Technology on Ground Control); Fisher's exact p=0.488, normalised score H=1.90 (p=0.594). ICC shows only exploration@T100 discriminates (0.717); outcome measures compress behavioural variance.

**The Sensorium Effect (PMR).** Agents massively under-monitor queryable state:
- Aggregate PMR 0.96–2.13%; victory monitoring only 0.05–0.29% (3.7–10.0 get_victory_progress calls/game)
- Despite playbook guidance to check every 20 turns, agents query every 30–75 turns
- **7 of 20 detectable defeats** — no victory-progress query in the 20-turn warning window
- PMR does not increase toward endgame (persistent allocation choice, not context limitation)

| Model | Defeats | Detectable | Queried | Missed |
|-------|---------|------------|---------|--------|
| Claude Opus 4.6 | 6 | 6 | 3 | 3 |
| Gemini 3.1 Pro | 5 | 5 | 4 | 1 |
| GPT-5.4 | 8 | 8 | 4 | 4 |
| Kimi-K2.5 | 1 | 1 | 1 | 0 |
| **Total** | **20** | **20** | **13** | **7** |

**Reflection–Action Gap (RAG@10).** RAG@10 ranges 48.2–65.8% across the three well-represented families (overlapping bootstrap CIs). Unexecuted commitments include "Build campuses in new cities", "Found second city", "Check victory progress". Commitments labelled by Claude Haiku 4.5; validated Cohen's κ=0.879.

**Tool-use profiles.** Local actions and state queries dominate; strategic monitoring stays uniformly low across models all game.

---

## 5. Limitations

- **Sample size/power:** 23 runs across 4 families, descriptive not statistically significant; Kimi has 1 run
- **Playbook confound:** shared guidance ⇒ deviations under instruction, not absence of capability; playbook-free baseline not viable (only 21% of pre-harness runs completed)
- **No random/scripted baseline** (future work)
- **Environmental:** Civ VI commercial licence required; FireTuner single-connection only; $31–229 API cost & 2–8 hrs per run; only Ground Control/Snowflake reported
- **Contamination:** strategy knowledge may be in training data, but evaluation targets live interaction
- **Measurement scope:** RAG depends on LLM-assisted labelling pipeline (κ=0.879); results are protocol-relative measurements

---

## 6. Cross-References to Cited Works

**Civ-based environments:**
- **CivRealm** (Qi et al., ICLR 2024 Spotlight) — FreeCiv engine, Gymnasium API; square grid, unit stacking, no districts/World Congress. CivBench contrasts: MCP interface, narration-layer controlled observability, richer Civ VI mechanics
- **CivAgent** (FuxiAILab 2024) — Unciv implementation
- **Vox Deorum** (Chen et al., arXiv 2512.18564, under review) — Civ V + Vox Populi, hybrid LLM+X (LLM strategy + algorithmic tactics); 2,327 games, two open-source LLMs tied win rates vs baseline but with distinct play styles

**LLM evaluation/agent benchmarks:**
- **BALROG** (Paglieri et al., ICLR 2025) — source of the explain-vs-execute gap; RAG@10 directly measures it
- **CICERO** (Meta FAIR, Science 2022, 10.1126/science.ade9097) — human-level Diplomacy play
- **Vending-Bench** (Andon Labs, arXiv 2502.15840) — long-term coherence over >20M tokens; consistent finding of long-horizon degradation
- **MCPAgentBench** (Liu et al., arXiv 2512.24565) — MCP tool-use efficiency across 180 tasks/20k tools
- **SWE-bench** (Jimenez et al., ICLR 2024) — contrasted as component-isolated evaluation
- **GameBench/GTBench/SMACv2** — shorter-horizon game & multi-agent benchmarks

---

## 7. Design Implications & Future Work

1. **Monitoring global state needs explicit mechanisms** — enforced query schedules, prioritised monitoring tools, or interfaces surfacing critical signals
2. **Persistent commitment tracking needed** — structured memory, task queues, or commitment enforcement
3. **Attention allocation is a distinct capability axis** for evaluation

Open questions: does structured reflection (diary) help or hurt? Ablations should test removing the diary, persistent commitment tracking, enforced monitoring schedules, and the Cry Havoc stress scenario; larger-scale reproduction needed.

---

## 8. Summary

CivBench fills a gap in evaluating long-horizon, tool-mediated agent behaviour via production-style MCP. Rather than ranking models, it introduces PMR and RAG@10, which reveal consistent failures: agents **systematically under-monitor critical state** and **fail to execute their own stated plans** — despite tool access and explicit guidance. Environment, logs, metrics, and analysis pipeline are fully open-source, providing a foundation for studying agent reliability in long-horizon tool-mediated settings.

---

*Compiled 2026-09-08. Paper read via arXiv PDF; repo details via GitHub MCP (crossref/openalex/pubmed) and API. Cross-references verified against Semantic Scholar, Google Scholar, and ICLR/OpenReview.*


