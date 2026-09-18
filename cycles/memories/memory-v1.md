# Strategy Notes - Next Solo Europe FFA Player
Format: Europe Normal, FFA Singleplayer, Easy, 52 nations + 400 tribes, no infinite gold/troops, no instant build, no donations. 50 ticks per decision.

## Last Match Result (ENGINE01)
- 158 decisions, tick 53 to 7903, 448 tool calls, ~1414s. Winner: none. Returncode 1.
- Human (Smoke): 74,969 tiles, 1,793,557 troops. Alive, mid-pack.
- Leaders to beat:
  - Algeria 259,122 tiles / 496,570 troops (tile leader, thin troops per tile)
  - Belarus 257,568 / 1,648,434
  - Serbia 199,375 / 1,596,451
  - Russia 166,740 / 1,908,627
  - Kazakhstan 162,683 / 880,054
  - Croatia 120,934 / 2,160,676 (densest large holder)
  - Netherlands 109,849 / 1,754,911
  - Ireland 78,192 / 3,910,659 (biggest stockpile, turtle - do not head-butt)
  - Libya 60,583 / 1,640,804
  - Sápmi 117,851 / 558,082, Estonia 106,073 / 797,423, Hungary 120,448 / 375,162
- Human was ~29% of Algeria/Belarus tiles, ~45% of Russia. Gap: ~184k tiles behind winner.
- 20 nations at 0 tiles but not all at 0 troops: Czechia 174,024, Bulgaria 80,328, Scotland 55,774, Poland 38,192, France 27,237, Monaco 23,385 etc. Dead land, live stacks - cleanup costs real troops.
- Sub-2k survivors are dead walking: Egypt 801 / 193k, Denmark 1095 / 187k, Belgium 1554 / 359k, Andorra 1580 / 99k, Greece 1920 / 195k, Slovakia 3857 / 133k. Never finish the game down here.

## What Won Tiles
- Neutral/tribe expansion early. 400 tribes means free land if you keep expanding while nations fight each other. Human stalled at 74k - leaders tripled it by eating neutrals + collapsed nations.
- Target thin holders: Algeria 259k tiles on only 496k troops (~1.9 troops/tile), Hungary 120k on 375k (~3.1/tile), Sápmi 117k on 558k. Same tiles for far fewer casualties than Croatia (~17.8/tile) or Ireland (~50/tile).
- Let others eliminate: 20 nations already at 0 tiles without you. Sweep 0-tile remnants with small forces, not main stack.

## What Bled Troops
- Head-on vs stockpiles: Ireland 3.9M, Croatia 2.16M, Russia 1.9M, Netherlands 1.75M, Belarus 1.64M, Libya 1.64M, Serbia 1.59M all out-stacked the human 1.79M at the end. Any single full-commit attack on these bleeds you white while a third party eats your border.
- Cleaning 0-tile ghosts: Czechia still held 174k troops with 0 tiles, Bulgaria 80k, Scotland 55k. Expect 50-170k cost per cleanup if you chase them.
- Attacks without shared border retreat silent. Only bordering tribes are even listed - distant orders waste a decision.
- Boat attacks and warship patrols only pay on water in the right component. Bad water tiles are rejected by the engine, costing tempo.

## When To Strike
- Strike nations when troops/tiles is low and alive but weak: e.g. Hungary, Algeria, Sápmi, Kazakhstan profiles above. Avoid Ireland/Croatia/Russia/Netherlands until you hold 150k+ tiles and 2.5M+ troops.
- Strike 0-tile nations only with surplus after you hold 100k+ tiles. Do not trade your core stack for Czechia-style 174k remnant stacks early.
- Keep ~2.8 orders per decision tempo (last match: 448 calls / 158 decisions). Every decision without an expand or well-picked nation attack is 50 ticks gifted to Algeria/Belarus/Serbia growth.
- Finish before tick 7903. Last match ran full 158 decisions with no winner. If you are still at 75k tiles by decision 100, you are losing - go thinner-target aggression, not turtling.

## Never Repeat
- Never turtle to 74k tiles / 1.79M troops and accept mid-pack survival. That is ~184k tiles short. Survival is not winning on this format.
- Never head-butt Ireland (78k tiles, 3.9M troops), Croatia (120k, 2.16M), Russia (166k, 1.9M) with parity stack. You lose the attrition and Algeria/Belarus walk away on tiles.
- Never sit in sub-10k tiles hoping troops save you. Egypt/Denmark/Belgium/Andorra/Greece prove <2k tiles + 100-350k troops is elimination in place.
- Never order expand vs distant tribe/nation without shared border, donate to strangers (friendly/allied only, silently refused), or expect alliances to answer on your schedule - recipient AI answers late or never.
- Never rely on upgrades for ports/missile-silo/sam/city/factory only, and remember delete has a grace period (unit stays listed briefly). Do not double-order.
