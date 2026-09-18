# Solo FFA (nations + tribes): one order per 50-tick decision

## Ethos
- Score is final standing, not peak tiles. Never drain home below a reserve that covers the strongest bordering non-ally; that is how runs die.
- Spend every decision: expand, raid a spent neighbour, boat, build, or defend. Idling gives a full refill of tempo to timed AIs.
- Growth compounds through maxTroops, not gold: max ~= 2*(tiles^0.6*1000+50000) + 250000*city levels (Medium nation x0.75, tribe x1/3); income is a flat ~100 gold/tick regardless of tiles.
- Fight the timer: a stronger target is worth hitting only if someone else is already breaking it (dogpile) or you must cancel its wave.
- Water is not a wall: 3 free boats. A run that stalls on land borders with boats idle is losing.

## When to act
- RIVAL CADENCE: a Medium nation runs its whole bundle (attack, diplomacy, structures) once every 55-70 ticks (Hard 45-60, Impossible 30-50); tribes every 40-80 and grab neutral land each cycle. Extra structure calls fire at 1/3 and 2/3 between acts.
- SPEND WINDOW: reserve is 30-40% of max, trigger 50-60%. A nation attacks only if troops >= reserve, and is guaranteed only at >= trigger (between the two, ~10%/act); the wave leaves it near reserve. The decision its troops cliff-drop is your window; hit it then. It cannot answer until it refills past reserve and trigger (55-70+ ticks).
- TRIBES need 50-60% of their max to launch a player attack, so draining a tribe under ~half its max silences it even faster.
- RETALIATE (forced): if the largest incoming attack's owner borders you, attack that owner this decision with at least its incoming count - attacks cancel troop-for-troop, and a larger alpha cancels then presses. A non-bordering attacker is unreachable by land: boat its boat_target, or ally it (an accepted alliance makes its ongoing attack retreat).
- ALLY: request when your troops >2.5x theirs (threat overrides even Hostile), relation Friendly, tick <1900, or you are comparable (troops >~0.7x theirs / tiles >~0.8x theirs with troops > half). Medium refuses below Neutral and keeps only ~4-5 alliances; it answers on its cadence. Tribes accept everything - ally bordering non-hostiles as shields and renew before the ~3000-tick expiry (only you can request renewal).
- DEFENSE POSTS: a nation builds one (Medium 50%/structure call, 1 total; Hard/Impossible ceil(ratio/0.4)) once its total LAND incoming >=35% of its troops; boat attacks never count. In range 30 a post multiplies your per-tile loss x5 and triples per-tile time. So keep land alphas under 35% of its D, or land >30 tiles away, or come by boat, or kill it before the 50-tick construction completes.
- DOGPILE: a target with incoming_troops >0.5x its troops and troops <=1.2x yours is the engine's victim - race it; under 100 tiles its land splits among attackers. If your own incoming total >0.5x your troops, stop attacking and defend or ally.
- BOAT: whenever neutral or weak land is only across water, launch this decision from boat_targets (3 free ships). A landing is an ordinary land strike from the shore, sized like any attack, and it never triggers a post.

## Attack sizing (derive everything; never a fixed share)
- D=target troops, T=target tiles, density D/T; m=80 plains/100 highland/120 mountain. Terrain is hidden: budget m=80 and pad 25-50% for highland/mountain.
- m_eff = m x0.7 vs tribe/bot, x5 within 30 tiles of an enemy defense post.
- a = clamp(D/A, 0.6, 2);  L = m_eff*(0.48a + 0.0052*D/T);  clear cost ~= L*T.
- Size A in [D, 1.7D], and A <= troops - reserve. Below D/2 the clamp doubles your loss; above 1.7D the clamp floors (0.6) and extra troops buy no exchange, only tie-ups. At A~1.7D, cost ~= m_eff*(0.288T + 0.0052D). Low density is cheap, high density expensive.
- One decisive alpha per target: nations regenerate every tick (fastest mid-range), so a slow two-wave grind refills the defender and re-pays the clamp. If it holds, switch targets.
- Neutral land: no defender, loss = m/5 per tile (16/20/24 plains/highland/mountain). Send at least the patch cost; unspent troops return if the patch clears, but an attack that runs out of troops is deleted, not refunded.
- Worked, tribe D=40k/T=1000 plains (m_eff=56), send 60k (a=0.67): L=56*(0.32+0.21)=30/tile -> ~30k clears.
- Worked, nation D=200k/T=4000 plains, send 300k (a=0.67): L=80*(0.32+0.26)=46/tile -> ~186k clears; with its post in range m_eff=400 -> ~930k: boat or skip.
- Worked, neutral 1000 plains + 300 highland: 16k + 6k = 22k; send ~22k plus margin.
