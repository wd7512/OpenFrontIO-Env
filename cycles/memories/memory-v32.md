# Procedural playbook — run this loop every decision

## Every decision, in order
1. `get_overview` before ordering. Read: troops, tiles, gold, `incoming_attacks`, `attacks`, `nations`, `tribes_list`, `boat_targets`, `units`.
2. DEFEND FIRST — if any incoming attack is >= 20% of your troops:
   - its attacker borders you: order an attack at that attacker with MORE than its troops (head-on attacks cancel troop-for-troop at launch; your surplus keeps advancing);
   - its attacker does not border you: build a defense-post on that front, or boat the attacker;
   - if the counter would strip home below your strongest bordering non-allied nation, send what you can and let a natural attack finish instead of cancelling.
3. ATTACK — fill up to two live attacks:
   - a bordering tribe: 1.3 x its troops;
   - else a bordering nation with troops <= 2/3 of yours: 1.3 x its troops;
   - else a neutral border: `expand` with max(8000, 8% of your troops).
   - Prefer a target whose troops just dropped (tiles flat, troops ~15-25% below last decision = it just spent; its counter is empty).
   - Never send more than 1.7 x the target's troops, and never drop home below your strongest bordering non-ally.
4. BUILD — if gold >= the next city price, build a city; else if an invaded front has no defense-post within 30 tiles and gold >= 50k, build one. Unspent gold is lost tempo: cities are +250k cap each.
5. BOATS — keep up to three transport ships moving at shores with reachable `boat_targets`; a landed boat becomes a free land attack.
6. `end_decision`. Never end a decision with zero orders: if nothing else, expand or upgrade.

## Standing rules
- Land share decides the game; a decision with no live attack is a lost decision. Going passive after the opening is the #1 way to lose.
- Max troops = 2*(tiles^0.6*1000 + 50,000) + 250,000 per city level; regen is fastest well below cap, so keep spending troops down.
- Per-tile loss: 0.48*clamp(D/A,0.6,2)*m + 0.52*(D/T)*(m/100); m = 80 plains/100 highland/120 mountain; x5 within 30 tiles of a defense post; x0.7 vs tribes.
- A nation acts every 55-70 ticks and attacks only at 50-60% of its cap: strike right after it spends.
- Attacking a nation is -70 relation plus an embargo: finish it or do not start it.
- Alliances: ask only neighbors you will not attack; a nation accepts when your troops > 2.5x its.
