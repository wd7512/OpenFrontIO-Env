# Solo FFA vs nations+tribes — one order per 50-tick (5 s) decision

## Ethos
- Score is final standing, not peak tiles. Never drain home to feed a front; keep a reserve that covers the strongest non-ally that borders you.
- Every decision, do exactly one thing: expand, raid a spent/weak neighbour, build/upgrade, boat, or defend. Idle decisions waste a full refill of tempo, and against nations that refill on a timer, idling means falling permanently behind.
- Growth is compounding: tiles raise maxTroops, cities raise it far more, and conquest hands you the loser's structures and gold. Prefer eating weak neighbours over trading with the strong.
- The run that stalls on water is a losing run. If land borders close, boats are how expansion continues — three free ships are wasted if they are not sailing.
- Fight the timer, not the wall. A stronger target is only worth hitting if someone else is already breaking it (dogpile) or you must cancel its wave.

## When to act
- RIVAL CADENCE: Medium nations run `maybeAttack` every 55–70 ticks; tribes every 40–80. Each run needs troops/max >= reserve (30–40%); only at trigger (50–60%) is a wave guaranteed, otherwise ~10% chance. A nation's troop count climbing while its tiles are flat is refilling; pinned near max means its wave is imminent.
- COUNTER WINDOW: its land wave removes everything above reserve from home at launch. Attack the decision you see its troops drop; draining it back under reserve silences it 55–70 ticks. Sending more troops than its current incoming to that attacker cancels troop-for-troop and keeps pressing.
- FORCED RETALIATION: if one incoming attack >= ~half your army, or it is the largest and its attacker borders you, spend the decision on it. Send >= that count back. A non-bordering attacker cannot be reached by land — boat one of its `boat_targets`, or ally it and an accepted alliance makes its ongoing attack retreat.
- ALLIANCE ACCEPT (Medium): accept if your troops > 2.5x theirs (threat overrides even Hostile relation), or relation Friendly, or it is early (< ~tick 1800) at ~70%, or they are similarly strong (their troops+outgoing > ~70% of yours, or their tiles > ~80% yours and their troops > half yours). Refuse if relation < Neutral, if you are a traitor, or once they hold ~4–5 alliances. Tribes accept everything — ally bordering non-hostiles early as shields, and renew before the 3000-tick expiry (only you can request). An ally out-trooping you ~10x may betray.
- DEFENSE POSTS (land only): a Medium nation gets 1 post, 50% per structure call (3 calls per act), only once land incoming >= 35% of its troops; boat attacks never count. Keep each land alpha under 35% of its troops, or strike > 30 tiles from the post, or come by boat. In range 30 a post multiplies your per-tile loss x5 and triples per-tile time — never grind one.
- DOGPILE: a bordering target with `incoming_troops` > 0.5x its troops and troops <= 1.2x yours is the engine's victim — race it; under 100 tiles it collapses and its land splits among attackers. If your own incoming total > 0.5x your troops, stop attacking and ally or retreat.
- BOAT TRIGGER: when neutral land and weak targets are only reachable across water, send a boat that same decision to the nearest `boat_targets` under ~30 tiles. A landing resolves as a land strike from the shore, so it can start a post; never let a shore sit unused.

## Attack sizing (never a fixed share)
- Land loss per tile: L = 0.6*clamp(D/A,0.6,2)*m*0.8 + 0.4*1.3*(D/T)*(m/100), where D = target troops, T = target tiles, A = attack troops, m = 80 plains / 100 highland / 120 mountain, x0.7 when the target is a tribe/bot, x5 if a defender defense post sits within 30 tiles. Clear cost ~= L*T.
- Terrain is not exposed to you: budget m=80 and pad 25–50% for highland/mountain tiles.
- Size A in [D, 1.7D]. Below D/2 the clamp doubles your loss; above 1.7D you only reach the 0.6 floor. A target with D > ~1.7x your available force is not clearable — hit it only to cancel a wave.
- Launch only if cost <= troops - reserve, with reserve >= strongest bordering non-ally and >= ~35% of your max. An attack that runs out of troops is deleted, not refunded; one that exhausts its border returns survivors (manual cancel costs 25% vs a player, free vs neutral land).
- One wave per target: if the target holds after one strike, switch targets. Repeated waves into one strong nation pay the clamp penalty each time and feed retaliation.
- Neutral land: loss = m/5 per tile (16/20/24 plains/highland/mountain), no defender loss; send ~= cost and top up rather than starving it.
- Worked, tribe D=60k, T=1500 plains: L ~= 27 + 12 = 39, so ~58k clears — send ~D=60k.
- Worked, nation D=200k, T=3000 plains: L ~= 38 + 28 = 66, so ~200k clears; with its post in range, L ~= 330 (~1M) — boat or skip.
- Worked, neutral 1000 plains / 3000 highland: 16k / 60k.
