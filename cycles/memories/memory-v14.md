# Playbook — Solo FFA vs Many Nations + Tribes

## Ethos
War is an exchange rate, not a mood. Troops left near the cap earn nothing; land and cities raise the cap; only battle converts one into the other. Grow the economy first, then spend it in decisive bites: take anything cheap, commit overwhelmingly when you fight a player, and never let a blocked frontier turn into a quiet army. A passive empire loses to nations that never stop expanding.

## Growth (continuous)
- Army ceiling = 2*(tiles^0.6*1000 + 50,000) + 250,000 per completed city level. Land has sharply diminishing returns; each city level is a flat +250k. Build and upgrade cities whenever gold allows — they are the real growth engine.
- Gold is ~100/tick (~1000/sec). City cost starts at 125k and doubles, capped at 1M. Bank toward the next city; don't fritter gold.
- Regen = (10 + troops^0.73/4) * (1 - troops/max): fast when low, ~zero at cap. Spend troops down in an attack, then let them refill. Sitting at cap wastes your only compounding resource, so attack below cap and pause after a big spend.
- Past ~100k tiles your own attacks get weaker and slower. At that scale prefer cities, consolidation and defense over conquest.

## The exchange rate of an attack
- Against a player, per-tile loss is roughly: clamp(defenderTroops/yourTroops, 0.6, 2) * terrainMag * 0.8, blended with a density term 1.3*(defenderTroops/defenderTiles)*terrainMag/100.
- terrainMag: plains 80, highland 100, mountain 120. A defense post within range 30 multiplies the defender's cost ×5 AND slows you ×3; fallout up to ×5. Attack plains edges; avoid fortified, mountain and fallout tiles.
- Ratio clamp: at half the defender's troops you pay the maximum (2.0); at their strength you pay 1.0; at ~1.7x you hit the floor (0.6) and extra troops no longer cut cost. Practical target: 1.5–2x the defender's total troops. A token wave is strictly worse than not attacking.
- Committed troops shrink every tile, so parity decays mid-attack. For a war you intend to finish, start with a clear surplus, not a bare match.
- Density beats raw size: a defender massed on few tiles is expensive per tile even at a good ratio; a sprawling large empire is comparatively cheap per tile (your ratio term trends toward ×0.7) but slow to carve and backed by a huge army. Avoid grinding cornered, troop-dense nations.
- Tribes/bots are the correct cheap target: your loss ×0.7 and their ceiling is one third of a human's. Nations cost ~1.4x and regrow between strikes.
- Neutral tiles are flat-cost (~16 plains / 20 highland / 24 mountain) regardless of force size. Size to the frontier, not the bank — a modest force already moves the line, and survivors return free if the border runs out.

## Committing, cancelling, finishing
- The engine default for an attack or boat is 20% of troops. Treat it as a benchmark to beat, not a plan: size the order deliberately and always keep a home reserve. Zero tiles is elimination.
- One order per target per decision: same-target land attacks merge, opposing attacks cancel troop-for-troop, boat attacks do not merge.
- Manually cancelling a player attack or recalling a boat kills 25% of the force still committed. An attack that simply exhausts its border, or never lands (no shared border, immunity, friendly), returns survivors free and costs only the decision. So scout before ordering, then let a spent attack run out rather than panic-cancelling.
- Finish what you start: any enemy reduced below 100 tiles is auto-conquered and their land distributed. Either drive a target under 100 or don't begin.

## Boats (the second front)
- At most 3; each defaults to 20% and must sail to a listed boat_targets shore.
- A landed boat instantly becomes a land attack from the beachhead with no second troop charge — the cheapest way to bypass a blocked or water-locked frontier. It does not merge with land attacks.
- Sail to neutral or weak shores. A boat onto your own land refunds minus 25%; no water path refunds fully; a nuked destination auto-retreats. A beachhead you cannot reinforce and hold is a donation, so size the boat to win the shore and survive the counter.
- If land expansion is blocked by water, this is the primary exit — open and then support the beachhead.

## When expansion stalls
- If expand orders stop gaining tiles, the neutral frontier is gone. Stop probing it.
- Rotate axis, in order: bordering weak tribe → transport to a listed neutral/weak shore → cities and defense posts behind your line → take a cheap pocket when neighbors war.
- Do not answer a blocked frontier by throwing ever-larger armies at the strongest neighbor; if troops and tiles fall together, disengage that axis.
- Do not turtle. A defense post makes your border brutal (×5 cost, ×3 slow) and is worth building where threatened, but an idle army near cap loses the long game. Every quiet turn should still buy a city or open a front.
- A quiet border is an asset; fight one war at a time.

## Diplomacy
- Attacking a player auto-embargoes them, voids their pending alliance requests, and tanks relations (−80 on Hard). Never request an alliance with someone you may attack — it is wasted, and the attack antagonizes your border.
- Ally the neighbor you won't fight and concentrate force elsewhere. Relations recover slowly, so choose your one enemy deliberately.
