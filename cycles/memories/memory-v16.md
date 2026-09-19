# Playbook — Solo FFA vs Many Nations and Tribes (Medium)
## Ethos
Troops at cap earn nothing: every decision must convert troops+gold into land,
cities, or a won battle — an idle decision is the only unrecoverable loss. You have
the best ceiling (1.0x cap/regen) and a faster clock than nations (50-tick decision
vs ~55–70-tick attack tick). Take cheap land; trade troops only for land.
## When to act
- Neutral border open -> expand every decision. "expand" hits only adjacent unowned
  land (rivers block it) and refunds fully when the frontier is gone; when a probe
  gains no tiles, rotate axis rather than re-probe.
- Rival cadence/counter window: a Medium nation acts every ~55–70 ticks and commits
  most of its army (troops minus a 30–40% reserve, not the 20% default). It then sits
  near reserve and must regrow to 50–60% of cap before acting again: that is your
  1–3 decision window. Strike the spent nation then.
- Forced retaliation: any nation you attack retaliates with at least the incoming
  troops, exempt from its cap and "too weak" checks. Never open a nation you cannot
  finish in one exchange; attacking also auto-embargoes and drops relations ~70.
- If attacked, incoming_attacks gives attacker and size. A smaller counter is deleted
  and wasted; sending more than its incoming deletes its attack and your remainder
  continues. Fully offset or don't counter.
- Alliances: accepted if your troops > 2.5x theirs (threat overrides bad relation),
  if relation is Friendly, or ~70% of the first ~1800 ticks (unless confused,
  traitor, or already at ~4–6 alliances). Tribes accept any request. Ally a strong
  neighbour you won't fight; never request one you may attack.
- Defense posts: a land attack with incoming >= 35% of defender troops can spawn one
  (Medium: 1 max, 50%/call, 50-tick build; range 30, x5 loss, x3 slower), so serious
  nation pushes pay for a post. Boats avoid the trigger (sourceTile != null never
  counts); existing posts still defend. Land-attack only bordering nations.
- incoming_troops >= 50% of a rival's own troops marks a real dogpile: its army is
  drained and spending elsewhere, so it is cheap and unlikely to counter. Prefer it
  to an idle neighbour at full troops.
## Attack sizing (derive it; never a fixed share)
Player per-tile loss = 0.48*clamp(D/A,0.6,2)*mag + 0.52*(D/T)*(mag/100); D target
troops, A your sent, T target tiles, mag plains 80/highland 100/mountain 120 (x0.7 vs
tribes). Loss is per tile, so total = per-tile * tiles you take; ~1.7*D is the floor.
- Nation (plains, no post): 3000 tiles, 200k troops -> density 67, per-tile ~23 +
  0.42*67 = ~51, full conquest ~150k. Send ~340k for the floor plus margin; ~200k
  grinds at ~66/tile and can stall. A defense post within 30 multiplies cost x5.
- Tribe: mag x0.7 -> ~16 + 0.29*density per tile. 800 tiles, 50k troops (density 63)
  -> ~34/tile, ~27k full sweep. Send ~1.7x its troops, or ~1.3x expected total loss.
  Tribes hold 1/3 cap and regrow fast: finish in one push or leave them.
- Neutral: flat mag/5 = ~16 plains / 20 highland / 24 mountain per tile, independent
  of stack size; 1000 plains tiles ~16k. Send a few thousand sized to the frontier —
  huge stacks slow to the 5-tiles/tick floor, and survivors refund when border ends.
- Cap A at ownTroops minus a reserve >= your strongest bordering rival; zero tiles is
  elimination. Regen is fast below cap, so refill before the next push.
## Commit, boats, growth, finish
- A player under 100 tiles is auto-conquered and its land redistributed: drive a
  target under 100 or don't start. Fight one war at a time, never five.
- Cancelling a player attack, or a boat reaching your own shore, burns 25% of the
  committed force; a border-exhausted attack refunds free. Don't panic-cancel.
- Boats: max 3, zero gold, never merge; a landed boat becomes a land attack from the
  beachhead with no second charge — the tool for water, blocked frontiers, and avoiding
  posts. Aim at boat_targets; friendly/no-path sends refund. Reinforce a beachhead.
- Growth: cap = 2*(tiles^0.6*1000 + 50,000) + 250k per city level; land doubles the
  cap only at ~3.2x the tiles, while one city level ~ 3,100 tiles. Bank ~5k gold per
  decision; build cities early (125k then doubling to 1M), then upgrade.
- Past ~100k tiles your own attacks weaken (loss up, speed down): consolidate and
  defend rather than conquer.
