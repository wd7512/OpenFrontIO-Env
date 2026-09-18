# Playbook — Solo FFA vs Nations + Tribes

## Ethos
- Land share wins, not kills. An idle decision wastes regen you cannot recover: every decision must buy land, cities, or a won battle.
- Nations compound — their troop cap rises with land and cities, and they build ports, silos, nukes and alliances. Tribes cap at cap/3 and never scale; neutral land earns nothing. Farm tribes/neutral only early; the run is decided by killing nations, weakest and nearest first.
- Fight one war at a time and concentrate. Three or four simultaneous attacks each lose their exchange and stall; merged land attacks on one target, one push, is how a target dies.

## When to act
- Refill cadence: a Medium nation acts every 55–70 ticks, keeps a 30–40%-of-cap reserve, commits down to ~30–40% cap, then must regrow to 50–60% cap before acting again. Across decisions (50 ticks) a sharp troop drop means it just spent: its counter is ~0 and it usually won't even retaliate below its trigger. Strike then, not when it sits at 50–60% cap.
- Forced retaliation and the counter window: retaliation sends troops−reserve with no "too weak" gate (Medium). If its counter ≥ your attack, your attack is deleted and its remainder hits you; if your attack is larger, its counter is deleted and your remainder continues. Never open a nation you cannot out-size in the same exchange.
- Offset incoming: send more than an incoming attack's troops at that attacker and its attack is deleted with your remainder advancing; send less and your counter is deleted and wasted. Fully offset or don't.
- Alliances: a Medium nation accepts if you are >2.5× its troops (threat overrides relation), if relation is Friendly, before ~tick 1900 (70%), or if similarly strong (≥~70–80% its troops, or ≥~80–90% its tiles with ≥50% troops) — and it holds <4–5 allies. Request early, stay Friendly, never request a nation you may hit (attacking auto-embargoes and drops relation ~70). Tribes accept any request.
- Defense posts: a land attack (sourceTile null) with incoming ≥ 35% of defender troops can spawn one (Medium: 50%/call, one max, 50-tick build, 50k+). A post within range 30 makes every land tile there x5 loss and x3 slower. Keep a land raid under 35% to avoid one, or hit a front >30 tiles from any post.
- Boats dodge the post trigger entirely: only sourceTile-null attacks count, and a boat landing plus the land attack it becomes both carry sourceTile. Existing posts still give their x5 to any combat within 30, including a landing.
- Dogpile: a rival with incoming_troops ≥ 50% of its own troops is a victim — its army is already engaged and it counter-attacks poorly. Prefer it over an idle neighbor. If your own incoming sum reaches ~50% of your troops, stop expanding and offset/consolidate.

## Attack sizing (derive it; never a fixed share)
- Per-tile attacker loss vs a player: 0.48·clamp(D/A, 0.6, 2)·m + 0.52·(D/T)·(m/100). D = target troops, A = sent, T = target tiles, density = D/T, m = 80 plains / 100 highland / 120 mountain, ×0.7 vs a tribe (Bot). Total ≈ per-tile × tiles taken; as D/A rises the rate worsens, so under-sending grinds or stalls.
- Cheapest rate is A ≥ 1.67·D (clamp floor 0.6); beyond that only reserve is wasted. Hard cap: A ≤ ownTroops − strongest bordering rival's troops — never let a neighbor zero you. Regen is fast below cap, so refill before the next push.
- Finish or don't start: a player driven under 100 tiles is auto-conquered and its land redistributed.
- Tribe (m=56), 800 tiles, 50k troops (density 63): ≈35/tile at A=80k, ≈45 at A=50k; full sweep ≈28–36k. Send ~1.3–1.7× its troops (~70–85k), then finish in one push or leave it — never 300k, and don't leave it half-dead to regrow.
- Nation (plains, m=80), 3000 tiles, 200k troops (density 67): ≈53/tile at A=300k, ≈66 at A=200k; full conquest ≈150–200k plus its regen. Send ~1.3–1.7× its troops (~260–340k). A post within 30 multiplies both mag terms ×5, so land-attacking into one is a trap — open by boat or hit a clear axis.
- Neutral: loss is flat m/5 = 16 plains / 20 highland / 24 mountain per tile, independent of A. Send a few thousand sized to the frontier (≥~7–10k keeps the 5-tiles/tick speed floor); more changes neither loss nor speed. Survivors refund when the frontier closes.
- Highlands/mountains cost 25–50% more per tile and move slower; prefer plains axes. Apply the reserve rule to every send.

## Boats, defense, growth, finish
- Boats: max 3, zero gold, never merged with land attacks. A landing becomes a land attack from the beach, no second charge — the tool for water, blocked fronts and post-free openings; reinforce the beachhead. Reaching your own shore, or a cancelled/retreating boat, burns 25% of its troops; a no-path send refunds fully. Don't cancel casually and don't overload one boat.
- Growth: max troops = 2·(tiles^0.6·1000 + 50,000) + 250k per city level; land only doubles it at ~3.2× tiles, so build cities early (125k/250k/500k then 1M) and bank gold every decision. Expect silos/nukes by mid-game — build SAM launchers and a defense post before then, and don't leave a strong border unallied forever.
- Past ~100k tiles your own attacks weaken (higher loss, slower); consolidate and defend instead of overreaching.
- Confirm an order can land before sending it: gold for builds, a shared border for land attacks, a reachable boat target. A rejected order burns the entire decision.
