# Idea: a learned 1v1 fighting policy ("IH body, RL brain")

## Status: sandbox built, probe positive, learning not started

## Problem
Improved-Hard is the best racer on The Box (paired solos: +1,685 ticks over
Hard, 6/6 seeds) but loses every fight: head-to-head duels went 0–6 to
production Hard, because `ImprovedHardExecution` only ever attacks
TerraNullius — it cannot retaliate, contest, or kill. Analysis:
`analysis/box_single_entity_baseline.md` (Duels section).

## Evidence fighting is the missing skill (not a different racer)
`analysis/probe_fight.py` (24 Box episodes, 4 scripted policies x 6 fresh
seeds, results in `analysis/results/probe_fight.json`):

| Policy | Wins | Notes |
|---|---|---|
| expand (= IH play) | 2/6 | wins take 47–102k-tick sieges |
| raid (15% at enemy / 52 ticks) | 6/6 | flips all 4 expand losses |
| commit (40% / 52 ticks) | 0/6 | overcommitting bleeds out — worse than pacifism |
| cycle (expand/raid/expand/commit) | 6/6 | fastest on every seed (7.6–8.5k ticks) |

Takeaways: the action space contains policies dominating the baseline on
every tested world; tempo matters more than tranche size; fight-games cost
~5s, so training episodes are cheap (measured sim throughput ~2k ticks/s).

## Proposal
Train a small discrete policy on the existing `DuelEnv`
(`src/openfrontbench/duel_env.py`, Gymnasium-shaped, no new deps):
agent nation (external @0) vs production Hard (@1), actions
{expand, raid, commit} at 52-tick cadence, ~8-field vector obs,
tiles-delta + terminal reward. Every episode tapes a standard record, so
training rollouts stay auditable through `scripts/verify_replay.ts`
(external tapes already verify FAITHFUL at Box scale, including a 60-order
fight episode).

## Suggested order
1. Mirror check: agent @1 (rule out side/spawn-slot bias in the probe).
2. PPO on `DuelEnv` (SB3 or minimal implementation) — start from
   cycle-behavior cloning, then let timing be learned.
3. Honest eval: fresh seeds, both sides, then self-play if it plateaus.
4. If it wins reliably: consider teaching target selection (>2 nations),
   then structures/diplomacy only if needed.

## Open questions
- Reward shaping: tiles-delta worked for scripts; learned policies may
  exploit turtling (long episodes already lose on ticks implicitly).
- Generalization beyond The Box (other maps, tribes, difficulties).
- Whether a learned policy beats the scripted `cycle` ceiling (~8k ticks)
  or just matches it more robustly.
