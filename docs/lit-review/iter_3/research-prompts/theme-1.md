# Theme 1 Brief: Harness Engineering — OpenFrontBench Lit Review

**Context:** `iter_1/proposal_v1.md` is `{proposal}`; questions are defined in
`../detailed_research_questions.md` and grouped in
`../grouped_research_questions.md`. Answer keyless and docs-grounded: primary
sources only, no LLM calls beyond the T6 runner, no network beyond cited
papers. This file is the exemplar — fullest of the ten briefs.

**Questions:** 1–6 ( §A harness attribution), 61–66 ( §K vendor pinning),
151–156 ( §Z paused boundaries and information scarcity).

**Task:** systematic review, not paper-by-paper summary. For every question:

- synthesise findings across multiple primary sources;
- separate empirical evidence from author opinion;
- note strengths, weaknesses, and assumptions of each method;
- surface consensus and conflicts, with reasons for disagreement;
- record gaps and unresolved questions.

**Evidence tables:** where quantitative results exist (ablation deltas,
replay-fidelity rates, cadence comparisons), summarise them in tables with
citations. Prefer CivBench, CivRealm, MCPAgentBench, and pinned-engine
precedents over generic harness commentary.

**Design implications:** close with concrete OpenFrontBench consequences —
server/worker split, pin-update policy, 50-tick cadence, query-purity and
rejection rules — each tied to the questions it answers.

**Report format** (per question):

```markdown
### Question
[verbatim question]
### Key Findings
- [finding + citation]
### Papers
1. [title] — [authors] ([year]). [DOI or URL]
### Gaps
[missing evidence]
### Relevance
[implication for OpenFrontBench]
```

**Honesty rules:** mark unverifiable claims pending; never fabricate LLM
performance; cite `references.bib` keys where applicable.
