# Solo FFA playbook — act every decision, size from the board

## Ethos
- One order per 50-tick decision; a no-op is a lost decision. Every decision do one of: expand neutral, hit a spent rival, or build/upgrade. Rivals spend their act tick too, so passivity hands them land.
- Growth is tiles + cities. maxTroops = 2*(tiles^0.6*1000+50000) + 250k per completed city level (Medium nation x0.75, tribe x1/3); gold is 100/tick, so convert it into cities/ports early and continuously. Land is the cap, structures are the multiplier and the shield.
- Finish wars. A survivor regens and stays Hostile; repeating the same oversized wave at it is the classic losing line — resize, boat, or switch. Cancelling an attack on a player burns 25% of the wave.
- Attacking a player is -70 relation, auto-embargo, and rejects their pending alliance request; the -20 embargo malus follows. Choose the alliance before the attack, never reject-then-attack a strong neighbor.
- Survival gates everything: while any wave is out, keep home above the strongest bordering non-ally. A Medium nation throws everything above 30-40% of max at its largest incoming attacker; a stripped home is unrecoverable.

## When to act
- CADENCE: a Medium nation acts every 55-70 ticks (tribe 40-80); it needs a 30-40% reserve to act and 50-60% of max to trigger without a 10% random pass. You decide every 50 ticks, so a rival that just acted is passive ~1-2 decisions. Refill is (10+troops^0.73/4)*(1-troops/max)*0.95/tick (x0.5 tribes); tiles flat while troops climb means refilling — strike as it nears its reserve, not after it re-arms.
- COUNTER WINDOW: a rival that just spent on you appears in incoming_attacks, so its act tick has passed and its next is 55-70 ticks away. Hit its homeland then; an attack of yours at it also cancels its incoming wave troop-for-troop at launch.
- FORCED RETALIATION: if one incoming attack is >= ~50% of your troops (or is the largest and borders you), send at least as much straight back at that attacker — it cancels their wave and pre-empts the counter. If the attacker does not border you, a land order just burns the tick and deepens the feud: boat or ally instead.
- ALLIANCES: threat overrides relation. A Medium nation accepts when your troops > 2.5x its (even Hostile), when relation is Friendly, when you look similarly strong (your troops + outgoing > 70-80% of its, or your tiles > 80-90% of its with troops > 0.5x), or before ~tick 1900 (~70%). Tribes accept everything. Ask before attacking, hold 4-6, extend before the 3000-tick lapse; traitors are refused. One strong border ally beats a raid.
- DEFENSE POSTS (land only): a Medium nation raises its one post when incoming LAND troops reach 35% of its current troops (50% chance per structure call at ~1/3 and 2/3 of its act interval; range 30, x5 your per-tile loss, x3 slower). Keep simultaneous land pressure below 35% of its troops, alpha one big first wave, or open a boat front — a landing has sourceTile set and never counts toward the 35%.
- DOGPILE: incoming_troops >= 50% of a rival's own troops is the engine's victim test; with its troops <= ~1.2x yours it is committed and counters weakly — hit it before an idle equal. At/above your count with heavy pressure it is collapsing; race to a border, because under 100 tiles it is auto-conquered and its land splits among adjacent players.
- BOATS: 3 max, 1 tile/tick; a landing ignores the post trigger, cancels the target's incoming attack, and opens a second front. Aim from boat_targets (owner/troops/tiles) at water-stalled fronts, islands and post-backed shores; keep all three moving, since recall/loss costs 25%.

## Attack sizing (derive A from D, T, terrain — never a fixed share)
- Per-tile loss vs a player: L = 0.6*(clamp(D/A,0.6,2)*m*0.8*def) + 0.4*(1.3*(D/T)*(m/100)), m = 80 plains/100 highland/120 mountain, x0.7 vs a tribe, x5 under a post; def = 0.7+0.3*defenseSig — ~1.0 below ~150k tiles, ~0.85 at 150k, 0.7 when very large. Clear cost is L*T plus regen (tens of k/decision): start only what finishes in 1-2 decisions.
- A = D is the knee (floor travel cost, max border progress); 1-1.7D is the efficient band. Under ~1D you pay up to ~2x per tile and can't outrun regen; over ~1.7D you strip home for nothing. The defender sheds D/T per tile, so clearing T tiles removes about D.
- Neutral: flat m/5 = 16/20/24 per tile; ~6600 plains / 8000 highland / 10000 mountain hits minimum travel cost, then moves ~0.4*frontier tiles/tick. Cost is per-tile x tiles; send more only across extra frontiers.
- Worked — tribe, 800 tiles/50k plains (m 56, def ~1): A=1.5D=75k -> clamp .67, L~36/tile -> ~29k to clear. A 15k probe -> clamp 2, L~72/tile, dies.
- Worked — nation, 3,000 tiles/200k plains (m 80, def ~1): A=1.4D=280k -> clamp .71, L~55/tile -> ~165k clear, one to two decisions. With a post L~275/tile (~825k): boat a clear shore or skip.
- Worked — big nation, 150k tiles/1.4M (def ~.85): D/T~9, L~27/tile -> ~4M to clear — more than a 1.4D wave, so hit it only while incoming_troops shows it collapsing.
- Worked — neutral, 1,000 plains: ~16/tile -> ~16k; send max(6600, frontier width), keep the rest home.
