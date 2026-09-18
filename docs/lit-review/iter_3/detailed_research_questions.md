# Detailed Research Questions — OpenFrontBench Lit Review

**Companion to:** `../iter_1/proposal_v1.md`
**Purpose:** 180 numbered research questions (30 sections A–AD × 6) grounding
every OpenFrontBench design choice in primary sources. The T6 batch parses
lines matching `^\s*(\d+)\.\s+`; keep that format exact.

---

## A. Harness Engineering and Attribution

1. What taxonomies of agent-harness engineering components exist in the literature, and how do they map onto OpenFrontBench's Python MCP server plus Node worker plus narration and telemetry split?
2. What empirical evidence links specific harness-component changes (orchestration, tool schemas, narration) to agent performance deltas, and which components matter most?
3. How have prior longitudinal harness studies attributed performance changes to individual commits, and what are the known limits of commit-level attribution under hosted-model drift?
4. What ablation designs isolate harness contributions from model-backbone contributions in tool-mediated agent evaluations?
5. What versioned-playbook patterns (decision-loop structure, checkpoints, diary discipline) have been shown to change agent behaviour, and how transferable are CivBench playbook findings to RTS tick boundaries?
6. How do isolated per-run agent configurations versus shared global configs affect reproducibility in harness studies?

---

## B. MCP Tool Surfaces and Discovery

7. What MCP tool-count and categorisation schemes (CivBench's 76 tools in 13 categories versus alternatives) best balance coverage against tool-selection errors?
8. How do tool-description verbosity, naming, and schema design affect LLM function-calling accuracy in game harnesses?
9. What distractor-tool and tool-selection-discrimination results from MCPAgentBench transfer to game-episode MCP surfaces?
10. How do stable ordered batches and idempotency protections for mutating actions affect measured agent reliability?
11. What error-recovery and retry patterns for failed tool invocations maximise end-to-end completion without inflating token cost?
12. How should infrastructure tools be categorised and excluded from behavioural metrics so PMR-style measures cannot be gamed?

---

## C. RTS versus 4X Evaluation Paradigms

13. How do real-time tick-based decision boundaries differ empirically from turn-based boundaries for measuring agent attention and planning?
14. What does the 4X evaluation literature (CivRealm, CivBench VI and V, Vox Deorum) report about long-horizon strategy measurement that transfers to RTS, and what does not?
15. How do fog-of-war, continuous time, and simultaneous moves in RTS games change evaluation design relative to turn-based 4X games?
16. What episode-length and tick-budget choices (for example 50-tick decisions, tick caps) best expose strategic differences without exploding run cost?
17. How do win-condition structures (territory and victory progress in RTS versus multi-path 4X victories) affect outcome-metric variance?
18. What prior RTS-agent benchmarks exist outside StarCraft micro, and what gaps does a full-game pinned-engine RTS benchmark fill?

---

## D. PMR at Tick Boundaries

19. How should Proactive Monitoring Rate be defined at tick boundaries (monitoring calls over non-infrastructure calls) so it stays comparable to CivBench's turn-based PMR?
20. What sensorium-effect evidence (CivBench PMR 1–2 percent, unqueried detectable defeats) predicts RTS under-monitoring, and how should warning-window analysis adapt from turns to ticks?
21. How do enforced query schedules versus voluntary monitoring change PMR, and what schedule cadences have empirical support?
22. How should voluntary versus forced or automatic monitoring calls be distinguished in logs so PMR stays honest?
23. What monitoring-tool prioritisation or critical-signal surfacing designs raise PMR without collapsing it into a forced metric?
24. How does PMR behave in smoke slices with no strategic-query events, and what null-reporting conventions avoid misleading zeros?

---

## E. RAG at Tick Boundaries

25. How should RAG at K be instantiated over the next-K tick decisions (rather than turns) while preserving CivBench's (Y + 0.5P) over commitments semantics?
26. What knowing-doing-gap evidence from BALROG and CivBench RAG at 10 (48–66 percent) predicts RTS commitment-execution failures?
27. What commitment-extraction pipelines (structured commitments versus free-text diary labelling, Claude Haiku kappa 0.879 precedent) are reliable for RTS diaries?
28. How do RAG window boundaries handle episode ends, agent death, tick caps, and budget stops without biasing scores?
29. When should RAG score N/A (no-diary or zero-commitment runs) rather than zero, and how do ablations test diary necessity?
30. How do commitment-tracking aids (task queues, enforcement, coach reminders) change execution fidelity in long-horizon tool-mediated play?

---

## F. Determinism, Replay and Tape

31. What deterministic-replay architectures (fixed seeds, manifest hashes, accepted-action replay) have proven sufficient for full-game strategy evaluations?
32. How should engine, map, config, and playbook manifest hashes be constructed and verified so replays are trustworthy across machines?
33. What RNG-consumption disciplines (queries never consume RNG, only advancing actions do) prevent observation from perturbing trajectories?
34. How do fresh-process replay checks with state hashes detect nondeterminism that single-process tests miss?
35. What trace formats (complete tool requests, results, status, tick and decision logs) best support offline rescore and third-party audit?
36. How do population and map-validity checks plus timeout and crash cleanup interact with replay guarantees?

---

## G. Grid-RLE Observation and Narration

37. What grid-encoding schemes (RLE, downsampling, region summaries) preserve strategically relevant RTS state within LLM context budgets?
38. How do narration layers (CivBench's 29 functions versus alternatives) affect agent situation awareness compared with raw state dumps?
39. What controlled-observability designs separate information availability from information retrieval so attention is measurable from traces?
40. How does observation granularity (per-tick versus per-decision snapshots) trade context cost against missed events?
41. What evaluator-only state separation patterns prevent observation leakage while keeping narration faithful?
42. How have prior RTS agents consumed spatial state (pixels, feature planes, symbolic grids), and what transfers to text-mediated MCP play?

---

## H. Smoke to 1v1 to Solo to Campaign Scaling

43. What staged scaling ladders (scripted smoke to 1v1 to solo to campaign) best de-risk harness development while keeping coverage labels honest?
44. How should restricted scenario and action coverage be labelled so smoke results are never mistaken for suite claims?
45. What paired spawn variants and fixed-seed suites control map luck while testing strategic generality?
46. How do opponent configurations (none, scripted, built-in AI, self-play) change measured capability at each scale stage?
47. What per-stage success criteria justify advancing (for example deterministic replay green, scripted full-game evidence) before spending LLM budget?
48. How do run cost, wall time, and API spend (CivBench 31–229 dollar per run precedent) scale with episode length and suite size?

---

## I. Coach, Retro and Memory Systems

49. What coach and retro memory architectures (post-episode distillation, cross-run playbook updates) improve RTS agents without hidden assistance?
50. How do five-field diary designs (tactical, strategic, tooling, planning, hypothesis) compare against unstructured logs for long-horizon coherence?
51. What RAG-memory designs (CivAgent-style lookahead simulators, episodic stores) transfer to tick-based RTS play?
52. How should diary storage outside model context be structured so memory ablations (no-diary baselines) stay clean?
53. What retrospective-analysis cadences (per-decision, per-game, per-suite) yield reusable strategy without leaking evaluator state?
54. How is memory help distinguished from hidden strategic assistance so coach systems stay within no-assist policy?

---

## J. Proxy Ledger and Provenance

55. What proxy-ledger designs record tool-request provenance (who called what, when, at which tick and decision) for audit?
56. How do token, call, wall-time, and retry ledgers attribute cost to decisions so efficiency metrics are reproducible?
57. What credential-hygiene patterns (key only in environment, never in logs) have proven sufficient for evaluation harnesses?
58. How do bounded-call, retry, and timeout records support fair comparison across providers and models?
59. What provenance must an offline-rescore input bundle contain so third parties can reproduce PMR and RAG without re-running agents?
60. How do ledger schemas evolve across harness versions without breaking historical comparisons?

---

## K. Vendor Pinning and Engine Fidelity

61. What vendoring and pinning policies (detached-head tags, recorded hashes, no upstream tracking) keep production-tick fidelity reproducible?
62. How do pinned-engine harnesses (OpenFrontIO v0.33.14 precedent) differ empirically from API-simulated or reimplemented game cores?
63. What upstream-update policies (deliberate bumps with full re-run) balance freshness against benchmark stability?
64. How do tribe and config execution declarations (never defaulting to TestConfig, preserving bot ticks) prevent silent fidelity loss?
65. What Node and Python dependency-locking practices keep the worker reproducible without mutating the vendor tree?
66. How is production-victory logic kept separate from tick-cap, agent-death, budget, and infra stops in reporting?

---

## L. CivRealm Baseline

67. What did CivRealm (FreeCiv plus Gymnasium, ICLR 2024 Spotlight) establish about imperfect-information general-sum Civ play that OpenFrontBench must account for?
68. How does CivRealm's Gymnasium interface compare with an MCP tool surface for measuring agent attention and tool-use correctness?
69. What diplomacy and natural-language communication findings from CivRealm transfer to RTS evaluation, and what do not?
70. How does CivRealm handle changing player counts and general-sum incentives, and what does that imply for OpenFrontBench 1v1 and campaign stages?
71. What are CivRealm's limits for behavioural metrics (no PMR or RAG), and how does adding tick-boundary PMR and RAG change what can be claimed?
72. What concrete design implications does CivRealm have for OpenFrontBench scenario and opponent design?

---

## M. Vox Deorum Baseline

73. What does Vox Deorum's hybrid LLM-plus-algorithmic architecture (LLM macro-strategy, algorithmic tactics, 2,327 Civ V games) imply for RTS agent decomposition?
74. How does Vox Deorum's MCP-server exposure of game state compare with OpenFrontBench's MCP surface, and what delegation-versus-direct-control lessons transfer?
75. What play-style divergence findings (tied win rates with distinct styles) warn against outcome-only RTS evaluation?
76. How does Vox Deorum evaluate long-horizon strategy without turn-level PMR or RAG scoring, and what would those metrics add?
77. What are the limits of a delegation model for measuring tool-use correctness at tick boundaries?
78. What concrete design implications does Vox Deorum have for OpenFrontBench narration and action validation?

---

## N. BALROG Baseline

79. What knowing-doing-gap evidence from BALROG (6 game environments, trajectory milestones) is the direct ancestor of RAG, and how does it instantiate in RTS?
80. How do BALROG's cross-environment milestone designs compare with OpenFrontBench's tick-boundary commitment tracking?
81. What reasoning-versus-execution dissociation results from BALROG predict RTS reflection-action gaps?
82. How does BALROG handle environment heterogeneity, and what does that imply for OpenFrontBench's smoke-to-campaign ladder?
83. What are BALROG's limits for MCP-specific tool-use measurement, and how does a unified RTS plus MCP surface extend it?
84. What concrete design implications does BALROG have for OpenFrontBench milestone and commitment schema design?

---

## O. Vending-Bench Baseline

85. What long-term-coherence findings from Vending-Bench (20M-plus token runs, behavioural goal-drift and meltdown loops) transfer from a vending sim to strategy games?
86. How does Vending-Bench justify RAG as a behavioural rather than architectural measure, and how does that argument land for RTS tick play?
87. What coherence-breakdown taxonomies from Vending-Bench apply to RTS diary and playbook drift?
88. How do Vending-Bench run lengths and cost profiles compare with projected OpenFrontBench campaign costs?
89. What are Vending-Bench's limits for strategy-game transfer (no adversaries, no spatial reasoning), and how does OpenFrontBench fill them?
90. What concrete design implications does Vending-Bench have for OpenFrontBench stall, loop, and drift detection?

---

## P. MCPAgentBench Baseline

91. What MCP harness-design lessons from MCPAgentBench (180 tasks, 20k tools, distractors, sandbox, completion plus efficiency) transfer to game-episode MCP evaluation?
92. How do MCPAgentBench tool-selection-discrimination and distractor-handling results map onto OpenFrontBench PMR (proactive selection) and rescore pipelines?
93. What efficiency-scoring designs from MCPAgentBench complement PMR and RAG without double-counting the same behaviour?
94. How does MCPAgentBench sandboxing compare with OpenFrontBench's isolated per-run config and no-shell policy for the playing agent?
95. What are MCPAgentBench's limits for long-horizon game episodes (mixed-horizon tasks versus full RTS games)?
96. What concrete design implications does MCPAgentBench have for OpenFrontBench tool catalogues and distractor discipline?

---

## Q. SWE-bench Contrast

97. How does SWE-bench's component-isolated patch evaluation (single-turn code fix, held-out tests) contrast paradigmatically with multi-turn tool-mediated RTS episodes?
98. What does SWE-bench's held-out-test scoring teach offline-rescore design for PMR and RAG?
99. How do contamination and memorisation critiques of SWE-bench (issue text revealing answers) inform OpenFrontBench map-seed and spawn-variety policy?
100. What cost, scale, and CI-integration lessons from SWE-bench transfer to a keyless real-engine test suite?
101. What are the limits of single-turn correctness metrics for measuring attention allocation and execution fidelity over hundreds of decisions?
102. What concrete design implications does the SWE-bench contrast have for OpenFrontBench's claim that it measures behaviour, not just outcomes?

---

## R. CICERO Baseline

103. What does CICERO (human-level Diplomacy, Science 2022, LM dialogue plus planning and RL) prove about LM-plus-search negotiation that RTS evaluation should test differently?
104. How do CICERO's cooperation and competition mechanisms map onto RTS diplomacy-free adversarial play, if at all?
105. What intent-modelling and communication findings from CICERO transfer to coach and diary-mediated RTS memory?
106. How does CICERO's evaluation (human-level play) compare with OpenFrontBench's behavioural-metric evaluation for claims about reliability?
107. What are CICERO's limits as a baseline (hidden assistance debates, no deterministic replay, no tool-mediated scoring)?
108. What concrete design implications does CICERO have for OpenFrontBench's no-assist policy and deterministic-replay claims?

---

## S. GameBench Baseline

109. What strategic-reasoning axes from GameBench (9 games) have empirical support, and which survive contact with live RTS fog and continuous time?
110. How do GameBench's short-horizon board and card evaluations compare with full-game RTS episodes for measuring planning depth?
111. What prompting and interface controls from GameBench transfer to paused tick-boundary evaluation?
112. How does GameBench score strategic reasoning beyond win rate, and what complements PMR and RAG?
113. What are GameBench's limits (no live RTS, no tool-mediated play, no replay), and how does OpenFrontBench fill them?
114. What concrete design implications does GameBench have for OpenFrontBench's strategy-axis reporting?

---

## T. GTBench Baseline

115. What game-theoretic task designs from GTBench (10 tasks) expose LLM strategic-reasoning limits relevant to RTS openings and expansions?
116. How do GTBench's equilibrium and opponent-modelling findings transfer to simultaneous-move RTS play?
117. What prompt-framing sensitivities reported by GTBench warn OpenFrontBench playbook and narration designers?
118. How does GTBench evaluate reasoning versus outcomes, and what complements tick-boundary behavioural metrics?
119. What are GTBench's limits (classical games, short horizons, no fog-of-war plus continuous time), and how does OpenFrontBench fill them?
120. What concrete design implications does GTBench have for OpenFrontBench's opponent-modelling and expansion-timing probes?

---

## U. SMACv2 Baseline

121. What cooperative-MARL evaluation lessons from SMACv2 (NeurIPS 2023, StarCraft II micro) transfer to full-game single-agent RTS evaluation?
122. How does SMACv2's scripted-wrapper approach compare with OpenFrontBench's full-game MCP plus diary episodes for measuring strategy?
123. What generalisation-probing designs (unit compositions, map variety) from SMACv2 inform OpenFrontBench spawn-variant policy?
124. How do SMACv2's episode metrics handle partial observability, and what transfers to grid-RLE plus narration observation?
125. What are SMACv2's limits (micro only, MARL wrapper, no tool-mediated play, no PMR or RAG)?
126. What concrete design implications does SMACv2 have for OpenFrontBench's solo and 1v1 stage design?

---

## V. CivBench VI Anchor

127. What makes CivBench VI (76 MCP tools, 300-plus turns, narration layer, PMR plus RAG at 10, 23 runs) the only entry with PMR and RAG ground truth in-repo, and what must a faithful RTS port preserve?
128. How do CivBench's sensorium-effect results (PMR 0.96–2.13 percent, victory monitoring 0.05–0.29 percent, 7 of 20 detectable defeats unqueried) set priors for RTS monitoring?
129. How do CivBench's RAG at 10 results (48.2–65.8 percent, overlapping bootstrap CIs) set priors for RTS execution fidelity?
130. How does CivBench's FireTuner live-game coupling compare with OpenFrontBench's persistent worker over a pinned core for determinism and cost?
131. What are CivBench's limits (commercial licence, single-connection FireTuner, 2–8 hours and 31–229 dollars per run, no random or scripted baseline) that OpenFrontBench must not inherit?
132. What concrete porting rules convert CivBench turn-level PMR and RAG into tick-level PMR and RAG without breaking comparability?

---

## W. CivBench V Baseline

133. What does CivBench V (307 multiplayer Civ V games, 7 LLMs, turn-level victory-probability estimation) contribute beyond victory-probability tracking for strategy evaluation?
134. How does progress-based evaluation compare with tool-use-correctness evaluation for claims about decision quality?
135. What multiplayer dynamics from CivBench V inform OpenFrontBench 1v1 and campaign design?
136. How do CivBench V's scale (hundreds of games) and cost per game compare with feasible OpenFrontBench suite sizes?
137. What are CivBench V's limits (no MCP tool integration, decision-quality focus rather than tool-use correctness)?
138. What concrete design implications does CivBench V have for OpenFrontBench victory-progress monitoring tools?

---

## X. CivAgent and Digital Player Baseline

139. What does CivAgent's digital-player design (Unciv, diplomacy skills, RAG memory, lookahead simulator, human-likeness focus) contribute to RTS agent architecture?
140. How does CivAgent's parallel tool-mediated idea (without MCP harness or monitoring metrics) compare with OpenFrontBench's MCP harness plus rescore?
141. What human-likeness evaluation methods from the digital-player work transfer to RTS play-style analysis?
142. How do lookahead-simulator memory designs handle branching futures, and what transfers to tick-based RTS planning?
143. What are CivAgent's limits (no MCP harness, no monitoring or execution metrics) that OpenFrontBench fills?
144. What concrete design implications does CivAgent have for OpenFrontBench coach memory and lookahead tooling?

---

## Y. Commitment Labelling and Diary Validation

145. How reliable is LLM-assisted commitment labelling (CivBench's Claude Haiku kappa 0.879 pipeline), and what replicates to free-text RTS diary validation?
146. What structured-commitment schemas support deterministic RAG scoring, and what labelling adaptation do they need for RTS diaries?
147. How should unsupported free-text labels be marked pending rather than fabricated, and what validation gates enforce that?
148. What diary-validation rules (five fields required non-empty, stored outside model context) keep memory ablations honest?
149. How do labelling disagreements get adjudicated, and what inter-rater reliability targets suit RTS commitment coding?
150. What Cry Havoc-style stress scenarios pressure-test commitment execution under Immortal-equivalent strain?

---

## Z. Paused Decision Boundaries and Information Scarcity

151. What evidence supports paused decision boundaries (queries never tick or consume RNG) as the cleanest way to separate sensing from acting in RTS evaluation?
152. How does the information-scarcity principle (the agent only knows what it explicitly queries) make attention allocation measurable, and what are its failure modes?
153. What decision-cadence evidence (for example 50 sim ticks per decision) balances strategic depth against run cost and context growth?
154. How do expand, attack-target-fraction, build-city-at-tile, and pass action abstractions trade expressiveness against invalid-input rates?
155. How should invalid and unknown inputs be rejected (with observable errors, without hidden assistance) so tool-use correctness is measurable?
156. How is sim time kept distinct from wall-clock timeouts in evaluation logic and reporting?

---

## AA. Offline Rescore and Manifests

157. What offline-rescore architectures reproduce outcome, PMR, and RAG at 10 from stored traces without re-running agents?
158. How do repeatable manifests (engine, map, config, playbook hashes) make individual and aggregate reports auditable?
159. What per-run log completeness rules (tool requests, results, status, tick, decision) are necessary and sufficient for rescore?
160. How do aggregate reports combine per-run PMR and RAG honestly across seeds, spawn variants, and scenarios?
161. What versioning discipline keeps rescore stable as harness, metrics, and diary schemas evolve?
162. How do rescore pipelines detect and report trace tampering or missing evaluator-only state?

---

## AB. Scenario and Map Design

163. What small-pinned-asset policies (genuine plains and big_plains, explicit populations and spawns) keep scenarios honest about coverage?
164. How do map-size facts (for example box-small mapping to 4.2M tiles) discipline scenario naming and reporting?
165. What spawn-design practices (fixed seeds plus paired variants) separate strategic skill from spawn luck?
166. How do population and resource configurations shape RTS strategic depth at smoke versus campaign scale?
167. What scenario-metadata standards (map hash, config hash, coverage labels) belong in every report?
168. How do map-generation and combat-formula documentations (upstream vendor docs) get verified rather than assumed?

---

## AC. Safety, Fairness and No-Assist Policy

169. What no-opponent-throttling and no-hidden-assistance rules keep RTS evaluation fair, and how are they verified in code and logs?
170. How do action-validation and turn-structure rules prevent the harness from playing the game for the agent?
171. What safety risks (unsafe tool use, resource exhaustion, log credential leaks) do keyless game harnesses face, and what mitigations have evidence?
172. How do fair-comparison rules (same versioned playbook, same seeds, same tick budgets) get enforced across providers and models?
173. What disclosure standards (restricted coverage, null metrics, pending labels) prevent overclaiming from smoke or partial runs?
174. How do safety and fairness checks run in CI without keys, network, or model access?

---

## AD. Evaluation Design, Statistics and Cost

175. What statistical treatments suit PMR and RAG comparisons across seeds and models (paired tests, bootstrap CIs, ICC-style discrimination analysis)?
176. How do outcome measures (wins, territory, victory progress) compress behavioural variance, and what reporting pairs outcomes with PMR and RAG?
177. What random and scripted baselines do strategy evaluations need before LLM results are interpretable, and what do they cost?
178. How do keyless CI suites (real-engine tests, entry-point smoke, protocol fixtures) stay meaningful without live-model validation?
179. What cost-modelling practices (per-run tokens, wall time, retry budgets) keep suite design inside budget before keys are spent?
180. What pre-registration and honest-limitation standards (no fabricated LLM performance, no literal Civ VI numerical-reproduction claims) govern reporting?

