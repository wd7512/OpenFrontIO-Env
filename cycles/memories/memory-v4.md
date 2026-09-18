# Strategy Notes - Next Solo Europe Run
Format: solo Europe Normal, Free For All Singleplayer, Easy, 52 nations + 400 tribes, full-res, seeded random land spawn, 50 ticks per decision.

Last match result at tick 5003 after 100 decisions: human Smoke 221059 tiles and 4393825 troops, no winner yet. Closest rivals Finland 134185 tiles and 1735864 troops, Russia 134663 tiles and 635328 troops, Kazakhstan 106979 tiles and 655971 troops, Sapmi 85267 tiles and 1097294 troops, Sweden 86306 tiles and 1323666 troops. Human led tiles by about 87000 over Finland and troops by about 2.6M over Finland. 13 nations at zero tiles: Switzerland, Egypt, Lebanon, Jordan, Spain, Albania, Syria, Austria, Turkiye, Northern Ireland, Slovakia, Romania, Germany. 309 tool orders across 100 decisions, about 3 per decision.

## What won tiles
- Early expand on adjacent neutral land won the bulk of the 221059 tiles. Expand resolves to empty land and does not split against a nation stack. Keep expand running while neutral ground borders you.
- Late game mass paid off: 4.39M troops banked let human hold a tile lead larger than any two mid nations combined. Do not stay thin. Bank then push.
- Tribes are 400 bodies on this format. Clearing bordering tribes one by one converts tiles cheap on Easy and removes raiders. Only bordering tribes are listed in overview, distant ones are unactionable.
- Cities, ports, factories compound. Ports and factories raise troop and gold flow that supports the 3-orders-per-decision tempo seen here. Prioritize economy buildings on owned land before long wars.

## What bled troops
- Attacks without a shared border retreat silent and waste the committed troops and a decision cycle. Check borders human flag before any nation or tribe attack.
- Splitting 1M max attack stacks across many nations bleeds. Top holders Israel 1562687 troops on 66100 tiles, Hungary 1239538 on 82308, Morocco 1081546 on 52426 show dense stacks. Hitting those head on without 2 to 1 local advantage stalls.
- Boats to bad tiles fail in engine validation. Water access and owned land rules apply. Confirm destination is reachable water component before committing boat troops.
- Donations to strangers are refused silent. Only allied friendly players can receive gold or troops. Do not gift to neutrals.

## When to strike
- Decisions 1 to 30, ticks about 53 to 1503: pure expand plus border tribe clears. No nation wars while under about 30000 tiles. Build economy.
- Decisions 30 to 70, ticks about 1500 to 3500: pick one bordering weak nation under 30000 tiles and under 500000 troops, example pattern Belgium 24731 tiles 310927 troops, Poland 24342 tiles 328255 troops. Finish it, then re-expand into the gap.
- Decisions 70 to 100, ticks 3500 to 5003: with over 150000 tiles and over 2M troops you can grind large holders like Finland, Russia, Sapmi. This match reached 221059 tiles by tick 5003 without a win check firing, so expect longer than 5000 ticks to close. Do not stop expanding between nation kills.
- Retreat is a real order. If an outgoing attack shows retreating or target stack doubles, cancel and redirect to expand the same decision window.

## What to never repeat
- Never attack nation number or tribe number you do not border. It auto retreats.
- Never leave expand idle while waiting on alliance answers. Recipient AI answers on its own schedule or never. Request once, keep expanding.
- Never embargo or break alliance casually. It cuts trade and donation path and draws attention with no tile gain.
- Never boat small packets repeatedly. One failed boat costs more than 10 expands. Save boats for true water crossings.
- Never chase zero tile ghosts with troops left, example Switzerland 8814 troops with 0 tiles, Egypt 19154 with 0 tiles, Spain 51658 with 0 tiles. They are dead, ignore and take land.
