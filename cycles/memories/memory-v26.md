# Solo FFA vs nations — one order per 50-tick decision, sized from the board

## Ethos
- Never idle: each decision is expand neutral, strike a spent/collapsed rival, or build/upgrade. A no-op leaves a maxed army rotting and hands tempo to rivals.
- Survival is the score. maxTroops = 2*(tiles^0.6*1000+50000) + 250k per city level (tribe /3, medium nation x0.75); income is only 100 gold/tick, so ports/factories pay for the rest. Keep home above the strongest bordering non-ally's army before every order.
- Land is the cap, cities the multiplier, captured structures the prize. Keep a steady build cadence; a thin economy (few cities, no port) cannot fund the army maxTroops promises.
- Finish or don't start: a survivor regens, stays Hostile (-70/attack, fades slowly) and keeps hitting you via `hated`. The classic losing line is raiding a big nation you failed to ally: it retaliates next act with all troops above its 30-40% reserve, and your under-sized wave gained nothing.
- Ally before you attack: an attack auto-embargos (-20) and rejects its pending alliance. Being >2.5x a nation lets you ally it even while Hostile — an off-ramp from war. Breaking an alliance makes you a traitor (30s, 0.5x defense) that nations refuse.
- A defense post (range 30) makes attackers lose ~5x per tile; one on your threatened front is the cheapest way to hold a border.

## When to act
- RIVAL CADENCE: a Medium nation acts every 55-70 ticks (tribe 40-80), only at >=30-40% of max troops and, 90% of the time, only at >=50-60% (10% random pass). Refill = (10+troops^0.73/4)*(1-troops/max)*0.95/tick. Flat tiles with troops climbing = refilling: strike as it nears its reserve, not after it re-arms. Pinned at ~max means an act is imminent.
- COUNTER WINDOW: its act tick is its biggest spend, so the decision after it attacks its home is short by that wave. Hit its home before its next 55-70-tick act. Launching at it cancels its attack troop-for-troop: send more than its incoming_attacks troops to cancel and still press; send less and your troops are consumed shrinking it.
- FORCED RETALIATION: if one incoming_attacks >= ~half your army, or is the largest and its attacker has borders_human, hit that attacker with at least its troop count. If it doesn't border you, a land order does nothing — boat or ally.
- ALLIANCES (Medium accepts when): your troops > 2.5x its (threat overrides even Hostile); relation Friendly; before tick ~1900 (70%); or similarly strong — your (troops+outgoing) > its total x0.7-0.8, or your tiles > its tiles x0.8-0.9 with your troops > its total x0.5. Refused when relation < Neutral (unless you're the threat), it already holds 4-5, or it's a traitor. Ask early, keep 4-5, extend before the 3000-tick lapse. A refusal is not a challenge: don't raid that nation unless its incoming_troops shows collapse.
- DEFENSE POSTS (land only): a Medium nation raises its one post when incoming LAND troops (sourceTile null; boat landings excluded) reach 35% of its troops, 50% per structure call, with calls at its act tick and ~1/3 and 2/3 through the interval. Land one alpha wave to stay under 35%, or open a boat front.
- BOATS: a landing has sourceTile set, so it never counts toward that 35% and can cancel the target's incoming attack. 3 max, 1 tile/tick. Aim from boat_targets (owner/troops/tiles) at post-backed shores and water-blocked fronts; keep all three moving — recall/loss costs 25%. Land attacks need a shared border; every other rival only by boat.
- DOGPILE: incoming_troops >= 50% of a rival's own troops is the engine's victim test, and only while its troops <= ~1.2x yours. Then it counters weakly — race to a border: under 100 tiles it is auto-conquered and its land splits among adjacent players. Also finish anyone under 15% of its max.

## Attack sizing (derive A each time from D=troops, T=tiles, terrain)
- Player: m = 80 plains / 100 highland / 120 mountain (x0.7 vs a tribe); def ~= 0.95 small, 0.85 at 150k tiles, 0.70 giant; x5 inside a post's range 30.
  L/tile ~= 0.6*[clamp(D/A,0.6,2)*m*0.8*def] + 0.4*[1.3*(D/T)*(m/100)]; clearing T tiles costs ~L*T (the defender sheds D/T per tile, so T tiles removes about D). Add tens of k of regen per decision.
- PRE-CHECK: if L*T exceeds your troops minus the home reserve, the attack cannot clear — don't launch it; it only marks you Hostile and feeds the enemy. A=D is the knee (clamp 1); the efficient band is 1-1.7D; below D/2 you pay the 2x clamp; above ~1.7D you strip home for little. Hard cap A = troops - strongest bordering non-ally's army.
- Neutral: flat m/5 = 16/20/24 per tile; send >= 6.6k plains / 8k highland / 10k mountain to expand at max speed (~0.4 frontier tiles/tick), and put spare troops on other frontiers, not the same one.
- Worked, tribe 800 tiles/50k plains: A=1.5D=75k -> clamp .67, L~36/tile -> ~29k to clear; a 15k probe clamps 2, ~72/tile, dies.
- Worked, nation 3,000 tiles/200k plains: A=1.4D=280k -> clamp .71, def~.97, L~54/tile -> ~163k to clear. With a post L~270/tile (~810k): boat a clear shore or skip.
- Worked, big nation 40k tiles/700k (def ~.94): D/T~17, L~65/tile -> ~2.6M to clear — no wave you can raise; hit it only while incoming_troops shows collapse, and mainly to cancel its counter.
- Worked, neutral 1,000 plains: ~16/tile -> ~16k; send max(6.6k, frontier width), keep the rest home.
