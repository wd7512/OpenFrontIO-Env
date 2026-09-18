# OpenFront solo playbook — every decision must buy land

## Ethos
- Land share wins; a decision with no live attack, boat, or build is forfeited. Never idle two decisions in a row.
- Regen = (10 + troops^0.73/4)*(1 - troops/max) collapses near the cap: ride at ~40-60% of max by spending into attacks, and keep a reserve above your strongest bordering non-ally.
- maxTroops = 2*(tiles^0.6*1000 + 50k) + 250k per city level. Territory raises the ceiling, so take land even when the exchange looks even.
- Read the fresh overview first. After ordering, confirm the attack/unit appears in `attacks`/`units` next decision; if it vanished it was blocked (immune, friendly, no shared border) — re-aim, never resend blindly, and never build twice on the same tile.
- Decide each bordering rival once: ally the ones you will never attack, attack the rest. Attacking costs -70 relation + an embargo and auto-rejects their alliance request; allying your own target blocks your attacks.

## When to act
- Refill cadence: Medium nations act every 55-70 ticks, tribes every 40-80. Each action dumps troops to 30-40% of max (10-20% on an expansion) then refills toward 50-60%. A rival whose troops drop sharply while tiles stay flat has just spent: that is the counter window — hit with ~1.7-2.2x its current troops. Do not open a big fight while its troops sit at 50-60% and climbing.
- Forced retaliation: if incoming_troops is >= ~20% of your troops, act this decision. Attacker borders you -> order a head-on attack >= its largest incoming attack; attacks cancel troop-for-troop at launch, so your surplus becomes the push. Attacker does not border you (boat) -> boat its source and/or post a defense post on the landing front; do not strip home.
- Alliances: a nation accepts when your troops > 2.5x its (threat overrides a hostile relation), when relation is Friendly, in the opening ~3 minutes (Medium: ~70% accept at relation >= Neutral), or when you are comparably strong; it rejects below Neutral or once it holds ~4-6 alliances. Request only from nations you will not attack. Tribes accept every request.
- Defense posts: a rival builds one only against land attacks (a boat landing carries a source tile and does not count) totalling >=35% of its troops; Medium builds one at 50% chance, harder modes ceil(ratio/0.4). So a land push of >=35% meets a post within ~1 decision (50-tick construction), while a boat landing does not trigger one. Inside a post's 30-tile range a push costs ~5x — pivot to an uncovered front or boat.
- Dogpile: a bordering rival with incoming_troops >= ~50% of its troops is being drained by others; join cheaply, it cannot counter and loses troops per tile you take. If your own incoming_troops is >= ~50% of your troops, you are the dogpile — stop advancing, counter the largest attacker, build a defense post.

## Attack sizing (never a fixed share)
- Neutral: ~16 plains / 20 highland / 24 mountain troops per tile. Value 20-25 x the tiles you mean to take; leftovers return when the front closes, and extra troops hardly speed neutral land while leaving home thin. Worked: 500 tiles ~ 8-12k.
- Player tiles: cost per tile ~= 0.6*clamp(D/A,0.6,2)*0.8*mag + 0.42*(D/T)*(mag/100), with D = target troops, T = target tiles (both readable), mag = 80/100/120 by terrain, x0.7 when the defender is a tribe, x5 inside a defender defense post.
- Size a push at A ~= 1.7-2.2*D: that reaches the clamp (D/A <= 0.6) for minimum loss per tile; below ~0.6*D you bleed badly. One push takes about A / (cost per tile) tiles, then refeed to finish.
- Prefer sprawling low-density targets: the (D/T) term is small and each tile you take also drains D/T of their troops. Compact high-density nations are expensive per tile.
- Worked tribe: D=5,000, T=2,000 (density 2.5), plains -> ~16/tile; A~10,000 takes ~600 tiles per push, a few pushes erases it.
- Worked nation: D=100,000, T=10,000 (density 10), plains -> ~27/tile; A=200,000 drains ~75k of their troops and takes ~7,000 tiles, then a ~50k follow-up finishes. Commit only when you can follow through.
- Terrain: attacks self-sort to the cheapest tiles first, so avoid mountain and post-covered fronts; plains are cheapest.

## Build and boats
- Spend all gold: cities are +250k cap each (125k, then doubling to 1M); a defense post pays off when land incoming reaches ~35% of your troops. Build on your own free tile — if the unit does not appear in `units` next overview the tile was invalid, so try another.
- Keep up to 3 transport ships sailing from shores to `boat_targets`; a landing becomes a free land attack (or seeds expansion on another landmass), avoids triggering rival defense posts, and is the only answer to water and straits. Ships move ~1 tile/tick, so launch early and far, and still avoid existing posts (they shell boats).
- Finish what you start: a half-finished nation refills and returns, and cancelling a land attack loses 25% of its troops — only cancel to save a front you can still hold.
