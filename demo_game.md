# Demo game transcript — Human (P1) + 3 AI

Config: `game.yaml` (seed 42, 2 dice, edition classic). Players: P1=human, P2=llm:mock:bayesian_probabilist, P3=llm:mock:deceptive_misdirector, P4=baseline:heuristic

The human seat is driven by a scripted stdin here so the transcript is reproducible; the numbered menus are exactly what an interactive player sees.
LLM seats use the offline MockLLM (they follow the symbolic tool recommendation). Shown cards appear only because P1 was the suggester or the shower.

**Result:** winner = P3, solution = ['Prof. Plum', 'Candlestick', 'Hall'], turns = 42, illegal attempts = 0

```text
╭─ Board (+ = door, X = cellar, S/M/W/G/K/P = tokens) ─╮
│     012345678901234567890123                         │
│  0           WbbbbG                                  │
│  1  kkkkkk....bbbb....cccccc                         │
│  2  kkkkkk..bbbbbbbb..cccccc                         │
│  3  KITCHk..bbbbbbbb..CONSEc                         │
│  4  kkkkkk..BALLROOb..cccccc                         │
│  5  kkkkkk.+bbbbbbbb+.cccccc                         │
│  6  kkkkkk..bbbbbbbb..+....K                         │
│  7   ...+...bbbbbbbb.......                          │
│  8   ........+....+...iiiiii                         │
│  9  dddddddd.........+iiiiii                         │
│ 10  dddddddd.XXXXXX...BILLIi                         │
│ 11  dddddddd.XXXXXX...iiiiii                         │
│ 12  DINING d+XXXXXX...iiiiii                         │
│ 13  dddddddd.XXXXXX.....+.+                          │
│ 14  dddddddd.XXXXXX..lllllll                         │
│ 15  dddddddd.XXXXXX..lllllll                         │
│ 16   .....+..XXXXXX.+LIBRARl                         │
│ 17  M..........++....lllllll                         │
│ 18   .....+..hhhhhh..lllllll                         │
│ 19  lllllll..hhhhhh........P                         │
│ 20  lllllll.+hhhhhh..+.....                          │
│ 21  LOUNGEl..hHALLh..sssssss                         │
│ 22  lllllll..hhhhhh..sSTUDYs                         │
│ 23  lllllll..hhhhhh..sssssss                         │
│ 24  lllllllS hhhhhh  sssssss                         │
╰──────────────────────────────────────────────────────╯
You are P1 (Miss Scarlet) at 24,7  hand: Col. Mustard, Lead Pipe, Mr. Green, Revolver, Wrench
         Notebook         
┏━━━━━━━━━━━━━━━┳━━━━━━━━┓
┃ Card          ┃ Status ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━┩
│ Miss Scarlet  │ ?      │
│ Col. Mustard  │ mine   │
│ Mrs. White    │ ?      │
│ Mr. Green     │ mine   │
│ Mrs. Peacock  │ ?      │
│ Prof. Plum    │ ?      │
│ Candlestick   │ ?      │
│ Dagger        │ ?      │
│ Lead Pipe     │ mine   │
│ Revolver      │ mine   │
│ Rope          │ ?      │
│ Wrench        │ mine   │
│ Hall          │ ?      │
│ Lounge        │ ?      │
│ Dining Room   │ ?      │
│ Kitchen       │ ?      │
│ Ballroom      │ ?      │
│ Conservatory  │ ?      │
│ Billiard Room │ ?      │
│ Library       │ ?      │
│ Study         │ ?      │
└───────────────┴────────┘
  [0] roll
  [1] ACCUSE (choose suspect + weapon + room)
Your action #: 0
P1 rolled [5, 3] = 8
╭─ Board (+ = door, X = cellar, S/M/W/G/K/P = tokens) ─╮
│     012345678901234567890123                         │
│  0           WbbbbG                                  │
│  1  kkkkkk....bbbb....cccccc                         │
│  2  kkkkkk..bbbbbbbb..cccccc                         │
│  3  KITCHk..bbbbbbbb..CONSEc                         │
│  4  kkkkkk..BALLROOb..cccccc                         │
│  5  kkkkkk.+bbbbbbbb+.cccccc                         │
│  6  kkkkkk..bbbbbbbb..+....K                         │
│  7   ...+...bbbbbbbb.......                          │
│  8   ........+....+...iiiiii                         │
│  9  dddddddd.........+iiiiii                         │
│ 10  dddddddd.XXXXXX...BILLIi                         │
│ 11  dddddddd.XXXXXX...iiiiii                         │
│ 12  DINING d+XXXXXX...iiiiii                         │
│ 13  dddddddd.XXXXXX.....+.+                          │
│ 14  dddddddd.XXXXXX..lllllll                         │
│ 15  dddddddd.XXXXXX..lllllll                         │
│ 16   .....+..XXXXXX.+LIBRARl                         │
│ 17  M..........++....lllllll                         │
│ 18   .....+..hhhhhh..lllllll                         │
│ 19  lllllll..hhhhhh........P                         │
│ 20  lllllll.+hhhhhh..+.....                          │
│ 21  LOUNGEl..hHALLh..sssssss                         │
│ 22  lllllll..hhhhhh..sSTUDYs                         │
│ 23  lllllll..hhhhhh..sssssss                         │
│ 24  lllllllS hhhhhh  sssssss                         │
╰──────────────────────────────────────────────────────╯
You are P1 (Miss Scarlet) at 24,7  hand: Col. Mustard, Lead Pipe, Mr. Green, Revolver, Wrench
         Notebook         
┏━━━━━━━━━━━━━━━┳━━━━━━━━┓
┃ Card          ┃ Status ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━┩
│ Miss Scarlet  │ ?      │
│ Col. Mustard  │ mine   │
│ Mrs. White    │ ?      │
│ Mr. Green     │ mine   │
│ Mrs. Peacock  │ ?      │
│ Prof. Plum    │ ?      │
│ Candlestick   │ ?      │
│ Dagger        │ ?      │
│ Lead Pipe     │ mine   │
│ Revolver      │ mine   │
│ Rope          │ ?      │
│ Wrench        │ mine   │
│ Hall          │ ?      │
│ Lounge        │ ?      │
│ Dining Room   │ ?      │
│ Kitchen       │ ?      │
│ Ballroom      │ ?      │
│ Conservatory  │ ?      │
│ Billiard Room │ ?      │
│ Library       │ ?      │
│ Study         │ ?      │
└───────────────┴────────┘
  [0] move to=16,7
  [1] move to=17,6
  [2] move to=17,8
  [3] move to=18,5
  [4] move to=Hall
  [5] move to=Lounge
  [6] ACCUSE (choose suspect + weapon + room)
Your action #: 4
P1 moved 24,7 -> Hall
╭─ Board (+ = door, X = cellar, S/M/W/G/K/P = tokens) ─╮
│     012345678901234567890123                         │
│  0           WbbbbG                                  │
│  1  kkkkkk....bbbb....cccccc                         │
│  2  kkkkkk..bbbbbbbb..cccccc                         │
│  3  KITCHk..bbbbbbbb..CONSEc                         │
│  4  kkkkkk..BALLROOb..cccccc                         │
│  5  kkkkkk.+bbbbbbbb+.cccccc                         │
│  6  kkkkkk..bbbbbbbb..+....K                         │
│  7   ...+...bbbbbbbb.......                          │
│  8   ........+....+...iiiiii                         │
│  9  dddddddd.........+iiiiii                         │
│ 10  dddddddd.XXXXXX...BILLIi                         │
│ 11  dddddddd.XXXXXX...iiiiii                         │
│ 12  DINING d+XXXXXX...iiiiii                         │
│ 13  dddddddd.XXXXXX.....+.+                          │
│ 14  dddddddd.XXXXXX..lllllll                         │
│ 15  dddddddd.XXXXXX..lllllll                         │
│ 16   .....+..XXXXXX.+LIBRARl                         │
│ 17  M..........++....lllllll                         │
│ 18   .....+..hhhhhh..lllllll                         │
│ 19  lllllll..hhhhhh........P                         │
│ 20  lllllll.+hhhhhh..+.....                          │
│ 21  LOUNGEl..hHALLh..sssssss                         │
│ 22  lllllll..hShhhh..sSTUDYs                         │
│ 23  lllllll..hhhhhh..sssssss                         │
│ 24  lllllll. hhhhhh  sssssss                         │
╰──────────────────────────────────────────────────────╯
You are P1 (Miss Scarlet) at Hall  hand: Col. Mustard, Lead Pipe, Mr. Green, Revolver, Wrench
         Notebook         
┏━━━━━━━━━━━━━━━┳━━━━━━━━┓
┃ Card          ┃ Status ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━┩
│ Miss Scarlet  │ ?      │
│ Col. Mustard  │ mine   │
│ Mrs. White    │ ?      │
│ Mr. Green     │ mine   │
│ Mrs. Peacock  │ ?      │
│ Prof. Plum    │ ?      │
│ Candlestick   │ ?      │
│ Dagger        │ ?      │
│ Lead Pipe     │ mine   │
│ Revolver      │ mine   │
│ Rope          │ ?      │
│ Wrench        │ mine   │
│ Hall          │ ?      │
│ Lounge        │ ?      │
│ Dining Room   │ ?      │
│ Kitchen       │ ?      │
│ Ballroom      │ ?      │
│ Conservatory  │ ?      │
│ Billiard Room │ ?      │
│ Library       │ ?      │
│ Study         │ ?      │
└───────────────┴────────┘
  [0] end_turn
  [1] suggest (choose suspect + weapon)
  [2] ACCUSE (choose suspect + weapon + room)
Your action #: 1
  [0] Miss Scarlet
  [1] Col. Mustard
  [2] Mrs. White
  [3] Mr. Green
  [4] Mrs. Peacock
  [5] Prof. Plum
Suspect #: 0
  [0] Candlestick
  [1] Dagger
  [2] Lead Pipe
  [3] Revolver
  [4] Rope
  [5] Wrench
Weapon #: 4
P1 suggests: Miss Scarlet with the Rope in the Hall
  P2 can disprove...
  P2 showed the Rope to P1
╭─ Board (+ = door, X = cellar, S/M/W/G/K/P = tokens) ─╮
│     012345678901234567890123                         │
│  0           WbbbbG                                  │
│  1  kkkkkk....bbbb....cccccc                         │
│  2  kkkkkk..bbbbbbbb..cccccc                         │
│  3  KITCHk..bbbbbbbb..CONSEc                         │
│  4  kkkkkk..BALLROOb..cccccc                         │
│  5  kkkkkk.+bbbbbbbb+.cccccc                         │
│  6  kkkkkk..bbbbbbbb..+....K                         │
│  7   ...+...bbbbbbbb.......                          │
│  8   ........+....+...iiiiii                         │
│  9  dddddddd.........+iiiiii                         │
│ 10  dddddddd.XXXXXX...BILLIi                         │
│ 11  dddddddd.XXXXXX...iiiiii                         │
│ 12  DINING d+XXXXXX...iiiiii                         │
│ 13  dddddddd.XXXXXX.....+.+                          │
│ 14  dddddddd.XXXXXX..lllllll                         │
│ 15  dddddddd.XXXXXX..lllllll                         │
│ 16   .....+..XXXXXX.+LIBRARl                         │
│ 17  M..........++....lllllll                         │
│ 18   .....+..hhhhhh..lllllll                         │
│ 19  lllllll..hhhhhh........P                         │
│ 20  lllllll.+hhhhhh..+.....                          │
│ 21  LOUNGEl..hHALLh..sssssss                         │
│ 22  lllllll..hShhhh..sSTUDYs                         │
│ 23  lllllll..hhhhhh..sssssss                         │
│ 24  lllllll. hhhhhh  sssssss                         │
╰──────────────────────────────────────────────────────╯
You are P1 (Miss Scarlet) at Hall  hand: Col. Mustard, Lead Pipe, Mr. Green, Revolver, Wrench
           Notebook           
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Card          ┃ Status     ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ Miss Scarlet  │ ?          │
│ Col. Mustard  │ mine       │
│ Mrs. White    │ ?          │
│ Mr. Green     │ mine       │
│ Mrs. Peacock  │ ?          │
│ Prof. Plum    │ ?          │
│ Candlestick   │ ?          │
│ Dagger        │ ?          │
│ Lead Pipe     │ mine       │
│ Revolver      │ mine       │
│ Rope          │ held by P2 │
│ Wrench        │ mine       │
│ Hall          │ ?          │
│ Lounge        │ ?          │
│ Dining Room   │ ?          │
│ Kitchen       │ ?          │
│ Ballroom      │ ?          │
│ Conservatory  │ ?          │
│ Billiard Room │ ?          │
│ Library       │ ?          │
│ Study         │ ?          │
└───────────────┴────────────┘
  [0] end_turn
  [1] ACCUSE (choose suspect + weapon + room)
Your action #: 0
--- Turn 1: P2 ---
P2 rolled [1, 2] = 3
P2 moved 17,0 -> 17,3
--- Turn 2: P3 ---
P3 rolled [6, 4] = 10
P3 moved 0,9 -> Ballroom
P3 suggests: Mr. Green with the Dagger in the Ballroom
  P4 cannot disprove
  P1 can disprove...
P3 suggested Mr. Green / Dagger / Ballroom. You must show a card.
Showing Mr. Green
  P1 showed the Mr. Green to P3
--- Turn 3: P4 ---
P4 suggests: Mrs. White with the Revolver in the Ballroom
  P1 can disprove...
P4 suggested Mrs. White / Revolver / Ballroom. You must show a card.
Showing Revolver
  P1 showed the Revolver to P4
--- Turn 4: P1 ---
╭─ Board (+ = door, X = cellar, S/M/W/G/K/P = tokens) ─╮
│     012345678901234567890123                         │
│  0           .bbbb.                                  │
│  1  kkkkkk....bbbb....cccccc                         │
│  2  kkkkkk..bbbbbbbb..cccccc                         │
│  3  KITCHk..bbbbbbbb..CONSEc                         │
│  4  kkkkkk..BALLROOb..cccccc                         │
│  5  kkkkkk.+bWGbbbbb+.cccccc                         │
│  6  kkkkkk..bbbbbbbb..+....K                         │
│  7   ...+...bbbbbbbb.......                          │
│  8   ........+....+...iiiiii                         │
│  9  dddddddd.........+iiiiii                         │
│ 10  dddddddd.XXXXXX...BILLIi                         │
│ 11  dddddddd.XXXXXX...iiiiii                         │
│ 12  DINING d+XXXXXX...iiiiii                         │
│ 13  dddddddd.XXXXXX.....+.+                          │
│ 14  dddddddd.XXXXXX..lllllll                         │
│ 15  dddddddd.XXXXXX..lllllll                         │
│ 16   .....+..XXXXXX.+LIBRARl                         │
│ 17  ...M.......++....lllllll                         │
│ 18   .....+..hhhhhh..lllllll                         │
│ 19  lllllll..hhhhhh........P                         │
│ 20  lllllll.+hhhhhh..+.....                          │
│ 21  LOUNGEl..hHALLh..sssssss                         │
│ 22  lllllll..hShhhh..sSTUDYs                         │
│ 23  lllllll..hhhhhh..sssssss                         │
│ 24  lllllll. hhhhhh  sssssss                         │
╰──────────────────────────────────────────────────────╯
You are P1 (Miss Scarlet) at Hall  hand: Col. Mustard, Lead Pipe, Mr. Green, Revolver, Wrench
           Notebook           
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Card          ┃ Status     ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ Miss Scarlet  │ ?          │
│ Col. Mustard  │ mine       │
│ Mrs. White    │ ?          │
│ Mr. Green     │ mine       │
│ Mrs. Peacock  │ ?          │
│ Prof. Plum    │ ?          │
│ Candlestick   │ ?          │
│ Dagger        │ ?          │
│ Lead Pipe     │ mine       │
│ Revolver      │ mine       │
│ Rope          │ held by P2 │
│ Wrench        │ mine       │
│ Hall          │ ?          │
│ Lounge        │ ?          │
│ Dining Room   │ ?          │
│ Kitchen       │ ?          │
│ Ballroom      │ ?          │
│ Conservatory  │ ?          │
│ Billiard Room │ ?          │
│ Library       │ ?          │
│ Study         │ ?          │
└───────────────┴────────────┘
  [0] roll
  [1] ACCUSE (choose suspect + weapon + room)
Your action #: 0
P1 rolled [3, 3] = 6
╭─ Board (+ = door, X = cellar, S/M/W/G/K/P = tokens) ─╮
│     012345678901234567890123                         │
│  0           .bbbb.                                  │
│  1  kkkkkk....bbbb....cccccc                         │
│  2  kkkkkk..bbbbbbbb..cccccc                         │
│  3  KITCHk..bbbbbbbb..CONSEc                         │
│  4  kkkkkk..BALLROOb..cccccc                         │
│  5  kkkkkk.+bWGbbbbb+.cccccc                         │
│  6  kkkkkk..bbbbbbbb..+....K                         │
│  7   ...+...bbbbbbbb.......                          │
│  8   ........+....+...iiiiii                         │
│  9  dddddddd.........+iiiiii                         │
│ 10  dddddddd.XXXXXX...BILLIi                         │
│ 11  dddddddd.XXXXXX...iiiiii                         │
│ 12  DINING d+XXXXXX...iiiiii                         │
│ 13  dddddddd.XXXXXX.....+.+                          │
│ 14  dddddddd.XXXXXX..lllllll                         │
│ 15  dddddddd.XXXXXX..lllllll                         │
│ 16   .....+..XXXXXX.+LIBRARl                         │
│ 17  ...M.......++....lllllll                         │
│ 18   .....+..hhhhhh..lllllll                         │
│ 19  lllllll..hhhhhh........P                         │
│ 20  lllllll.+hhhhhh..+.....                          │
│ 21  LOUNGEl..hHALLh..sssssss                         │
│ 22  lllllll..hShhhh..sSTUDYs                         │
│ 23  lllllll..hhhhhh..sssssss                         │
│ 24  lllllll. hhhhhh  sssssss                         │
╰──────────────────────────────────────────────────────╯
You are P1 (Miss Scarlet) at Hall  hand: Col. Mustard, Lead Pipe, Mr. Green, Revolver, Wrench
           Notebook           
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Card          ┃ Status     ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ Miss Scarlet  │ ?          │
│ Col. Mustard  │ mine       │
│ Mrs. White    │ ?          │
│ Mr. Green     │ mine       │
│ Mrs. Peacock  │ ?          │
│ Prof. Plum    │ ?          │
│ Candlestick   │ ?          │
│ Dagger        │ ?          │
│ Lead Pipe     │ mine       │
│ Revolver      │ mine       │
│ Rope          │ held by P2 │
│ Wrench        │ mine       │
│ Hall          │ ?          │
│ Lounge        │ ?          │
│ Dining Room   │ ?          │
│ Kitchen       │ ?          │
│ Ballroom      │ ?          │
│ Conservatory  │ ?          │
│ Billiard Room │ ?          │
│ Library       │ ?          │
│ Study         │ ?          │
└───────────────┴────────────┘
  [0] move to=15,15
  [1] move to=15,8
  [2] move to=16,16
  [3] move to=16,7
  [4] move to=17,6
  [5] move to=18,16
  [6] move to=18,5
  [7] move to=19,15
  [8] move to=24,7
  [9] move to=Lounge
  [10] ACCUSE (choose suspect + weapon + room)
Your action #: 9
P1 moved Hall -> Lounge
╭─ Board (+ = door, X = cellar, S/M/W/G/K/P = tokens) ─╮
│     012345678901234567890123                         │
│  0           .bbbb.                                  │
│  1  kkkkkk....bbbb....cccccc                         │
│  2  kkkkkk..bbbbbbbb..cccccc                         │
│  3  KITCHk..bbbbbbbb..CONSEc                         │
│  4  kkkkkk..BALLROOb..cccccc                         │
│  5  kkkkkk.+bWGbbbbb+.cccccc                         │
│  6  kkkkkk..bbbbbbbb..+....K                         │
│  7   ...+...bbbbbbbb.......                          │
│  8   ........+....+...iiiiii                         │
│  9  dddddddd.........+iiiiii                         │
│ 10  dddddddd.XXXXXX...BILLIi                         │
│ 11  dddddddd.XXXXXX...iiiiii                         │
│ 12  DINING d+XXXXXX...iiiiii                         │
│ 13  dddddddd.XXXXXX.....+.+                          │
│ 14  dddddddd.XXXXXX..lllllll                         │
│ 15  dddddddd.XXXXXX..lllllll                         │
│ 16   .....+..XXXXXX.+LIBRARl                         │
│ 17  ...M.......++....lllllll                         │
│ 18   .....+..hhhhhh..lllllll                         │
│ 19  lllllll..hhhhhh........P                         │
│ 20  lllllll.+hhhhhh..+.....                          │
│ 21  LOUNGEl..hHALLh..sssssss                         │
│ 22  lSlllll..hhhhhh..sSTUDYs                         │
│ 23  lllllll..hhhhhh..sssssss                         │
│ 24  lllllll. hhhhhh  sssssss                         │
╰──────────────────────────────────────────────────────╯
You are P1 (Miss Scarlet) at Lounge  hand: Col. Mustard, Lead Pipe, Mr. Green, Revolver, Wrench
           Notebook           
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Card          ┃ Status     ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ Miss Scarlet  │ ?          │
│ Col. Mustard  │ mine       │
│ Mrs. White    │ ?          │
│ Mr. Green     │ mine       │
│ Mrs. Peacock  │ ?          │
│ Prof. Plum    │ ?          │
│ Candlestick   │ ?          │
│ Dagger        │ ?          │
│ Lead Pipe     │ mine       │
│ Revolver      │ mine       │
│ Rope          │ held by P2 │
│ Wrench        │ mine       │
│ Hall          │ ?          │
│ Lounge        │ ?          │
│ Dining Room   │ ?          │
│ Kitchen       │ ?          │
│ Ballroom      │ ?          │
│ Conservatory  │ ?          │
│ Billiard Room │ ?          │
│ Library       │ ?          │
│ Study         │ ?          │
└───────────────┴────────────┘
  [0] end_turn
  [1] suggest (choose suspect + weapon)
  [2] ACCUSE (choose suspect + weapon + room)
Your action #: 1
  [0] Miss Scarlet
  [1] Col. Mustard
  [2] Mrs. White
  [3] Mr. Green
  [4] Mrs. Peacock
  [5] Prof. Plum
Suspect #: 4
  [0] Candlestick
  [1] Dagger
  [2] Lead Pipe
  [3] Revolver
  [4] Rope
  [5] Wrench
Weapon #: 1
P1 suggests: Mrs. Peacock with the Dagger in the Lounge
  P2 can disprove...
  P2 showed the Dagger to P1
╭─ Board (+ = door, X = cellar, S/M/W/G/K/P = tokens) ─╮
│     012345678901234567890123                         │
│  0           .bbbb.                                  │
│  1  kkkkkk....bbbb....cccccc                         │
│  2  kkkkkk..bbbbbbbb..cccccc                         │
│  3  KITCHk..bbbbbbbb..CONSEc                         │
│  4  kkkkkk..BALLROOb..cccccc                         │
│  5  kkkkkk.+bWGbbbbb+.cccccc                         │
│  6  kkkkkk..bbbbbbbb..+.....                         │
│  7   ...+...bbbbbbbb.......                          │
│  8   ........+....+...iiiiii                         │
│  9  dddddddd.........+iiiiii                         │
│ 10  dddddddd.XXXXXX...BILLIi                         │
│ 11  dddddddd.XXXXXX...iiiiii                         │
│ 12  DINING d+XXXXXX...iiiiii                         │
│ 13  dddddddd.XXXXXX.....+.+                          │
│ 14  dddddddd.XXXXXX..lllllll                         │
│ 15  dddddddd.XXXXXX..lllllll                         │
│ 16   .....+..XXXXXX.+LIBRARl                         │
│ 17  ...M.......++....lllllll                         │
│ 18   .....+..hhhhhh..lllllll                         │
│ 19  lllllll..hhhhhh........P                         │
│ 20  lllllll.+hhhhhh..+.....                          │
│ 21  LOUNGEl..hHALLh..sssssss                         │
│ 22  lSKllll..hhhhhh..sSTUDYs                         │
│ 23  lllllll..hhhhhh..sssssss                         │
│ 24  lllllll. hhhhhh  sssssss                         │
╰──────────────────────────────────────────────────────╯
You are P1 (Miss Scarlet) at Lounge  hand: Col. Mustard, Lead Pipe, Mr. Green, Revolver, Wrench
           Notebook           
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Card          ┃ Status     ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ Miss Scarlet  │ ?          │
│ Col. Mustard  │ mine       │
│ Mrs. White    │ ?          │
│ Mr. Green     │ mine       │
│ Mrs. Peacock  │ ?          │
│ Prof. Plum    │ ?          │
│ Candlestick   │ ?          │
│ Dagger        │ held by P2 │
│ Lead Pipe     │ mine       │
│ Revolver      │ mine       │
│ Rope          │ held by P2 │
│ Wrench        │ mine       │
│ Hall          │ ?          │
│ Lounge        │ ?          │
│ Dining Room   │ ?          │
│ Kitchen       │ ?          │
│ Ballroom      │ ?          │
│ Conservatory  │ ?          │
│ Billiard Room │ ?          │
│ Library       │ ?          │
│ Study         │ ?          │
└───────────────┴────────────┘
  [0] end_turn
  [1] ACCUSE (choose suspect + weapon + room)
Your action #: 0
--- Turn 5: P2 ---
P2 rolled [2, 2] = 4
P2 moved 17,3 -> 18,6
--- Turn 6: P3 ---
P3 rolled [3, 1] = 4
P3 moved Ballroom -> 10,8
--- Turn 7: P4 ---
P4 rolled [1, 4] = 5
P4 moved Ballroom -> Conservatory
P4 suggests: Col. Mustard with the Wrench in the Conservatory
  P1 can disprove...
P4 suggested Col. Mustard / Wrench / Conservatory. You must show a card.
  [0] Col. Mustard
  [1] Wrench
Show card #: 0
  P1 showed the Col. Mustard to P4
--- Turn 8: P1 ---
╭─ Board (+ = door, X = cellar, S/M/W/G/K/P = tokens) ─╮
│     012345678901234567890123                         │
│  0           .bbbb.                                  │
│  1  kkkkkk....bbbb....cccccc                         │
│  2  kkkkkk..bbbbbbbb..cccccc                         │
│  3  KITCHk..bbbbbbbb..CONSEc                         │
│  4  kkkkkk..BALLROOb..cMGccc                         │
│  5  kkkkkk.+bbbbbbbb+.cccccc                         │
│  6  kkkkkk..bbbbbbbb..+.....                         │
│  7   ...+...bbbbbbbb.......                          │
│  8   ........+....+...iiiiii                         │
│  9  dddddddd.........+iiiiii                         │
│ 10  ddddddddWXXXXXX...BILLIi                         │
│ 11  dddddddd.XXXXXX...iiiiii                         │
│ 12  DINING d+XXXXXX...iiiiii                         │
│ 13  dddddddd.XXXXXX.....+.+                          │
│ 14  dddddddd.XXXXXX..lllllll                         │
│ 15  dddddddd.XXXXXX..lllllll                         │
│ 16   .....+..XXXXXX.+LIBRARl                         │
│ 17  ...........++....lllllll                         │
│ 18   .....+..hhhhhh..lllllll                         │
│ 19  lllllll..hhhhhh........P                         │
│ 20  lllllll.+hhhhhh..+.....                          │
│ 21  LOUNGEl..hHALLh..sssssss                         │
│ 22  lSKllll..hhhhhh..sSTUDYs                         │
│ 23  lllllll..hhhhhh..sssssss                         │
│ 24  lllllll. hhhhhh  sssssss                         │
╰──────────────────────────────────────────────────────╯
You are P1 (Miss Scarlet) at Lounge  hand: Col. Mustard, Lead Pipe, Mr. Green, Revolver, Wrench
           Notebook           
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Card          ┃ Status     ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ Miss Scarlet  │ ?          │
│ Col. Mustard  │ mine       │
│ Mrs. White    │ ?          │
│ Mr. Green     │ mine       │
│ Mrs. Peacock  │ ?          │
│ Prof. Plum    │ ?          │
│ Candlestick   │ ?          │
│ Dagger        │ held by P2 │
│ Lead Pipe     │ mine       │
│ Revolver      │ mine       │
│ Rope          │ held by P2 │
│ Wrench        │ mine       │
│ Hall          │ ?          │
│ Lounge        │ ?          │
│ Dining Room   │ ?          │
│ Kitchen       │ ?          │
│ Ballroom      │ ?          │
│ Conservatory  │ ?          │
│ Billiard Room │ ?          │
│ Library       │ ?          │
│ Study         │ ?          │
└───────────────┴────────────┘
  [0] roll
  [1] passage
  [2] ACCUSE (choose suspect + weapon + room)
Your action #: 1
P1 took the secret passage Lounge -> Conservatory
╭─ Board (+ = door, X = cellar, S/M/W/G/K/P = tokens) ─╮
│     012345678901234567890123                         │
│  0           .bbbb.                                  │
│  1  kkkkkk....bbbb....cccccc                         │
│  2  kkkkkk..bbbbbbbb..cccccc                         │
│  3  KITCHk..bbbbbbbb..CONSEc                         │
│  4  kkkkkk..BALLROOb..cSMGcc                         │
│  5  kkkkkk.+bbbbbbbb+.cccccc                         │
│  6  kkkkkk..bbbbbbbb..+.....                         │
│  7   ...+...bbbbbbbb.......                          │
│  8   ........+....+...iiiiii                         │
│  9  dddddddd.........+iiiiii                         │
│ 10  ddddddddWXXXXXX...BILLIi                         │
│ 11  dddddddd.XXXXXX...iiiiii                         │
│ 12  DINING d+XXXXXX...iiiiii                         │
│ 13  dddddddd.XXXXXX.....+.+                          │
│ 14  dddddddd.XXXXXX..lllllll                         │
│ 15  dddddddd.XXXXXX..lllllll                         │
│ 16   .....+..XXXXXX.+LIBRARl                         │
│ 17  ...........++....lllllll                         │
│ 18   .....+..hhhhhh..lllllll                         │
│ 19  lllllll..hhhhhh........P                         │
│ 20  lllllll.+hhhhhh..+.....                          │
│ 21  LOUNGEl..hHALLh..sssssss                         │
│ 22  lKlllll..hhhhhh..sSTUDYs                         │
│ 23  lllllll..hhhhhh..sssssss                         │
│ 24  lllllll. hhhhhh  sssssss                         │
╰──────────────────────────────────────────────────────╯
You are P1 (Miss Scarlet) at Conservatory  hand: Col. Mustard, Lead Pipe, Mr. Green, Revolver, Wrench
           Notebook           
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Card          ┃ Status     ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ Miss Scarlet  │ ?          │
│ Col. Mustard  │ mine       │
│ Mrs. White    │ ?          │
│ Mr. Green     │ mine       │
│ Mrs. Peacock  │ ?          │
│ Prof. Plum    │ ?          │
│ Candlestick   │ ?          │
│ Dagger        │ held by P2 │
│ Lead Pipe     │ mine       │
│ Revolver      │ mine       │
│ Rope          │ held by P2 │
│ Wrench        │ mine       │
│ Hall          │ ?          │
│ Lounge        │ ?          │
│ Dining Room   │ ?          │
│ Kitchen       │ ?          │
│ Ballroom      │ ?          │
│ Conservatory  │ ?          │
│ Billiard Room │ ?          │
│ Library       │ ?          │
│ Study         │ ?          │
└───────────────┴────────────┘
  [0] end_turn
  [1] suggest (choose suspect + weapon)
  [2] ACCUSE (choose suspect + weapon + room)
Your action #: 1
  [0] Miss Scarlet
  [1] Col. Mustard
  [2] Mrs. White
  [3] Mr. Green
  [4] Mrs. Peacock
  [5] Prof. Plum
Suspect #: 5
  [0] Candlestick
  [1] Dagger
  [2] Lead Pipe
  [3] Revolver
  [4] Rope
  [5] Wrench
Weapon #: 0
P1 suggests: Prof. Plum with the Candlestick in the Conservatory
  P2 cannot disprove
  P3 can disprove...
  P3 showed the Conservatory to P1
╭─ Board (+ = door, X = cellar, S/M/W/G/K/P = tokens) ─╮
│     012345678901234567890123                         │
│  0           .bbbb.                                  │
│  1  kkkkkk....bbbb....cccccc                         │
│  2  kkkkkk..bbbbbbbb..cccccc                         │
│  3  KITCHk..bbbbbbbb..CONSEc                         │
│  4  kkkkkk..BALLROOb..cSMGPc                         │
│  5  kkkkkk.+bbbbbbbb+.cccccc                         │
│  6  kkkkkk..bbbbbbbb..+.....                         │
│  7   ...+...bbbbbbbb.......                          │
│  8   ........+....+...iiiiii                         │
│  9  dddddddd.........+iiiiii                         │
│ 10  ddddddddWXXXXXX...BILLIi                         │
│ 11  dddddddd.XXXXXX...iiiiii                         │
│ 12  DINING d+XXXXXX...iiiiii                         │
│ 13  dddddddd.XXXXXX.....+.+                          │
│ 14  dddddddd.XXXXXX..lllllll                         │
│ 15  dddddddd.XXXXXX..lllllll                         │
│ 16   .....+..XXXXXX.+LIBRARl                         │
│ 17  ...........++....lllllll                         │
│ 18   .....+..hhhhhh..lllllll                         │
│ 19  lllllll..hhhhhh.........                         │
│ 20  lllllll.+hhhhhh..+.....                          │
│ 21  LOUNGEl..hHALLh..sssssss                         │
│ 22  lKlllll..hhhhhh..sSTUDYs                         │
│ 23  lllllll..hhhhhh..sssssss                         │
│ 24  lllllll. hhhhhh  sssssss                         │
╰──────────────────────────────────────────────────────╯
You are P1 (Miss Scarlet) at Conservatory  hand: Col. Mustard, Lead Pipe, Mr. Green, Revolver, Wrench
           Notebook           
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Card          ┃ Status     ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ Miss Scarlet  │ ?          │
│ Col. Mustard  │ mine       │
│ Mrs. White    │ ?          │
│ Mr. Green     │ mine       │
│ Mrs. Peacock  │ ?          │
│ Prof. Plum    │ ?          │
│ Candlestick   │ ?          │
│ Dagger        │ held by P2 │
│ Lead Pipe     │ mine       │
│ Revolver      │ mine       │
│ Rope          │ held by P2 │
│ Wrench        │ mine       │
│ Hall          │ ?          │
│ Lounge        │ ?          │
│ Dining Room   │ ?          │
│ Kitchen       │ ?          │
│ Ballroom      │ ?          │
│ Conservatory  │ held by P3 │
│ Billiard Room │ ?          │
│ Library       │ ?          │
│ Study         │ ?          │
└───────────────┴────────────┘
  [0] end_turn
  [1] ACCUSE (choose suspect + weapon + room)
Your action #: 0
--- Turn 9: P2 ---
P2 suggests: Prof. Plum with the Revolver in the Conservatory
  P3 can disprove...
  P3 showed a card to P2
--- Turn 10: P3 ---
P3 rolled [1, 3] = 4
P3 moved 10,8 -> Ballroom
P3 suggests: Prof. Plum with the Candlestick in the Ballroom
  P4 cannot disprove
  P1 cannot disprove
  P2 can disprove...
  P2 showed a card to P3
--- Turn 11: P4 ---
P4 rolled [3, 5] = 8
P4 moved Conservatory -> Billiard Room
P4 suggests: Prof. Plum with the Rope in the Billiard Room
  P1 cannot disprove
  P2 can disprove...
  P2 showed a card to P4
--- Turn 12: P1 ---
╭─ Board (+ = door, X = cellar, S/M/W/G/K/P = tokens) ─╮
│     012345678901234567890123                         │
│  0           .bbbb.                                  │
│  1  kkkkkk....bbbb....cccccc                         │
│  2  kkkkkk..bbbbbbbb..cccccc                         │
│  3  KITCHk..bbbbbbbb..CONSEc                         │
│  4  kkkkkk..BALLROOb..cSMccc                         │
│  5  kkkkkk.+bWbbbbbb+.cccccc                         │
│  6  kkkkkk..bbbbbbbb..+.....                         │
│  7   ...+...bbbbbbbb.......                          │
│  8   ........+....+...iiiiii                         │
│  9  dddddddd.........+iiiiii                         │
│ 10  dddddddd.XXXXXX...BILLIi                         │
│ 11  dddddddd.XXXXXX...iGPiii                         │
│ 12  DINING d+XXXXXX...iiiiii                         │
│ 13  dddddddd.XXXXXX.....+.+                          │
│ 14  dddddddd.XXXXXX..lllllll                         │
│ 15  dddddddd.XXXXXX..lllllll                         │
│ 16   .....+..XXXXXX.+LIBRARl                         │
│ 17  ...........++....lllllll                         │
│ 18   .....+..hhhhhh..lllllll                         │
│ 19  lllllll..hhhhhh.........                         │
│ 20  lllllll.+hhhhhh..+.....                          │
│ 21  LOUNGEl..hHALLh..sssssss                         │
│ 22  lKlllll..hhhhhh..sSTUDYs                         │
│ 23  lllllll..hhhhhh..sssssss                         │
│ 24  lllllll. hhhhhh  sssssss                         │
╰──────────────────────────────────────────────────────╯
You are P1 (Miss Scarlet) at Conservatory  hand: Col. Mustard, Lead Pipe, Mr. Green, Revolver, Wrench
           Notebook           
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Card          ┃ Status     ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ Miss Scarlet  │ ?          │
│ Col. Mustard  │ mine       │
│ Mrs. White    │ ?          │
│ Mr. Green     │ mine       │
│ Mrs. Peacock  │ ?          │
│ Prof. Plum    │ ?          │
│ Candlestick   │ ?          │
│ Dagger        │ held by P2 │
│ Lead Pipe     │ mine       │
│ Revolver      │ mine       │
│ Rope          │ held by P2 │
│ Wrench        │ mine       │
│ Hall          │ ?          │
│ Lounge        │ ?          │
│ Dining Room   │ ?          │
│ Kitchen       │ ?          │
│ Ballroom      │ ?          │
│ Conservatory  │ held by P3 │
│ Billiard Room │ ?          │
│ Library       │ ?          │
│ Study         │ ?          │
└───────────────┴────────────┘
Constraints: P3 has one of ['Prof. Plum', 'Revolver', 'Conservatory']; P2 has one of ['Prof. Plum', 
'Candlestick', 'Ballroom']; P2 has one of ['Prof. Plum', 'Rope', 'Billiard Room']
  [0] roll
  [1] passage
  [2] ACCUSE (choose suspect + weapon + room)
Your action #: 1
P1 took the secret passage Conservatory -> Lounge
╭─ Board (+ = door, X = cellar, S/M/W/G/K/P = tokens) ─╮
│     012345678901234567890123                         │
│  0           .bbbb.                                  │
│  1  kkkkkk....bbbb....cccccc                         │
│  2  kkkkkk..bbbbbbbb..cccccc                         │
│  3  KITCHk..bbbbbbbb..CONSEc                         │
│  4  kkkkkk..BALLROOb..cMcccc                         │
│  5  kkkkkk.+bWbbbbbb+.cccccc                         │
│  6  kkkkkk..bbbbbbbb..+.....                         │
│  7   ...+...bbbbbbbb.......                          │
│  8   ........+....+...iiiiii                         │
│  9  dddddddd.........+iiiiii                         │
│ 10  dddddddd.XXXXXX...BILLIi                         │
│ 11  dddddddd.XXXXXX...iGPiii                         │
│ 12  DINING d+XXXXXX...iiiiii                         │
│ 13  dddddddd.XXXXXX.....+.+                          │
│ 14  dddddddd.XXXXXX..lllllll                         │
│ 15  dddddddd.XXXXXX..lllllll                         │
│ 16   .....+..XXXXXX.+LIBRARl                         │
│ 17  ...........++....lllllll                         │
│ 18   .....+..hhhhhh..lllllll                         │
│ 19  lllllll..hhhhhh.........                         │
│ 20  lllllll.+hhhhhh..+.....                          │
│ 21  LOUNGEl..hHALLh..sssssss                         │
│ 22  lSKllll..hhhhhh..sSTUDYs                         │
│ 23  lllllll..hhhhhh..sssssss                         │
│ 24  lllllll. hhhhhh  sssssss                         │
╰──────────────────────────────────────────────────────╯
You are P1 (Miss Scarlet) at Lounge  hand: Col. Mustard, Lead Pipe, Mr. Green, Revolver, Wrench
           Notebook           
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Card          ┃ Status     ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ Miss Scarlet  │ ?          │
│ Col. Mustard  │ mine       │
│ Mrs. White    │ ?          │
│ Mr. Green     │ mine       │
│ Mrs. Peacock  │ ?          │
│ Prof. Plum    │ ?          │
│ Candlestick   │ ?          │
│ Dagger        │ held by P2 │
│ Lead Pipe     │ mine       │
│ Revolver      │ mine       │
│ Rope          │ held by P2 │
│ Wrench        │ mine       │
│ Hall          │ ?          │
│ Lounge        │ ?          │
│ Dining Room   │ ?          │
│ Kitchen       │ ?          │
│ Ballroom      │ ?          │
│ Conservatory  │ held by P3 │
│ Billiard Room │ ?          │
│ Library       │ ?          │
│ Study         │ ?          │
└───────────────┴────────────┘
Constraints: P3 has one of ['Prof. Plum', 'Revolver', 'Conservatory']; P2 has one of ['Prof. Plum', 
'Candlestick', 'Ballroom']; P2 has one of ['Prof. Plum', 'Rope', 'Billiard Room']
  [0] end_turn
  [1] suggest (choose suspect + weapon)
  [2] ACCUSE (choose suspect + weapon + room)
Your action #: 1
  [0] Miss Scarlet
  [1] Col. Mustard
  [2] Mrs. White
  [3] Mr. Green
  [4] Mrs. Peacock
  [5] Prof. Plum
Suspect #: 0
  [0] Candlestick
  [1] Dagger
  [2] Lead Pipe
  [3] Revolver
  [4] Rope
  [5] Wrench
Weapon #: 0
P1 suggests: Miss Scarlet with the Candlestick in the Lounge
  P2 cannot disprove
  P3 cannot disprove
  P4 can disprove...
  P4 showed the Lounge to P1
╭─ Board (+ = door, X = cellar, S/M/W/G/K/P = tokens) ─╮
│     012345678901234567890123                         │
│  0           .bbbb.                                  │
│  1  kkkkkk....bbbb....cccccc                         │
│  2  kkkkkk..bbbbbbbb..cccccc                         │
│  3  KITCHk..bbbbbbbb..CONSEc                         │
│  4  kkkkkk..BALLROOb..cMcccc                         │
│  5  kkkkkk.+bWbbbbbb+.cccccc                         │
│  6  kkkkkk..bbbbbbbb..+.....                         │
│  7   ...+...bbbbbbbb.......                          │
│  8   ........+....+...iiiiii                         │
│  9  dddddddd.........+iiiiii                         │
│ 10  dddddddd.XXXXXX...BILLIi                         │
│ 11  dddddddd.XXXXXX...iGPiii                         │
│ 12  DINING d+XXXXXX...iiiiii                         │
│ 13  dddddddd.XXXXXX.....+.+                          │
│ 14  dddddddd.XXXXXX..lllllll                         │
│ 15  dddddddd.XXXXXX..lllllll                         │
│ 16   .....+..XXXXXX.+LIBRARl                         │
│ 17  ...........++....lllllll                         │
│ 18   .....+..hhhhhh..lllllll                         │
│ 19  lllllll..hhhhhh.........                         │
│ 20  lllllll.+hhhhhh..+.....                          │
│ 21  LOUNGEl..hHALLh..sssssss                         │
│ 22  lSKllll..hhhhhh..sSTUDYs                         │
│ 23  lllllll..hhhhhh..sssssss                         │
│ 24  lllllll. hhhhhh  sssssss                         │
╰──────────────────────────────────────────────────────╯
You are P1 (Miss Scarlet) at Lounge  hand: Col. Mustard, Lead Pipe, Mr. Green, Revolver, Wrench
           Notebook           
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Card          ┃ Status     ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ Miss Scarlet  │ ?          │
│ Col. Mustard  │ mine       │
│ Mrs. White    │ ?          │
│ Mr. Green     │ mine       │
│ Mrs. Peacock  │ ?          │
│ Prof. Plum    │ ?          │
│ Candlestick   │ ?          │
│ Dagger        │ held by P2 │
│ Lead Pipe     │ mine       │
│ Revolver      │ mine       │
│ Rope          │ held by P2 │
│ Wrench        │ mine       │
│ Hall          │ ?          │
│ Lounge        │ held by P4 │
│ Dining Room   │ ?          │
│ Kitchen       │ ?          │
│ Ballroom      │ ?          │
│ Conservatory  │ held by P3 │
│ Billiard Room │ ?          │
│ Library       │ ?          │
│ Study         │ ?          │
└───────────────┴────────────┘
Constraints: P3 has one of ['Prof. Plum', 'Revolver', 'Conservatory']; P2 has one of ['Prof. Plum', 
'Candlestick', 'Ballroom']; P2 has one of ['Prof. Plum', 'Rope', 'Billiard Room']
  [0] end_turn
  [1] ACCUSE (choose suspect + weapon + room)
Your action #: 0
--- Turn 13: P2 ---
P2 took the secret passage Conservatory -> Lounge
P2 suggests: Mrs. Peacock with the Revolver in the Lounge
  P3 cannot disprove
  P4 can disprove...
  P4 showed a card to P2
--- Turn 14: P3 ---
P3 rolled [3, 1] = 4
P3 moved Ballroom -> 10,8
--- Turn 15: P4 ---
P4 rolled [6, 4] = 10
P4 moved Billiard Room -> Conservatory
P4 suggests: Mrs. White with the Dagger in the Conservatory
  P1 cannot disprove
  P2 can disprove...
  P2 showed a card to P4
--- Turn 16: P1 ---
╭─ Board (+ = door, X = cellar, S/M/W/G/K/P = tokens) ─╮
│     012345678901234567890123                         │
│  0           .bbbb.                                  │
│  1  kkkkkk....bbbb....cccccc                         │
│  2  kkkkkk..bbbbbbbb..cccccc                         │
│  3  KITCHk..bbbbbbbb..CONSEc                         │
│  4  kkkkkk..BALLROOb..cWGccc                         │
│  5  kkkkkk.+bbbbbbbb+.cccccc                         │
│  6  kkkkkk..bbbbbbbb..+.....                         │
│  7   ...+...bbbbbbbb.......                          │
│  8   ........+....+...iiiiii                         │
│  9  dddddddd.........+iiiiii                         │
│ 10  dddddddd.XXXXXX...BILLIi                         │
│ 11  dddddddd.XXXXXX...iPiiii                         │
│ 12  DINING d+XXXXXX...iiiiii                         │
│ 13  dddddddd.XXXXXX.....+.+                          │
│ 14  dddddddd.XXXXXX..lllllll                         │
│ 15  dddddddd.XXXXXX..lllllll                         │
│ 16   .....+..XXXXXX.+LIBRARl                         │
│ 17  ...........++....lllllll                         │
│ 18   .....+..hhhhhh..lllllll                         │
│ 19  lllllll..hhhhhh.........                         │
│ 20  lllllll.+hhhhhh..+.....                          │
│ 21  LOUNGEl..hHALLh..sssssss                         │
│ 22  lSMKlll..hhhhhh..sSTUDYs                         │
│ 23  lllllll..hhhhhh..sssssss                         │
│ 24  lllllll. hhhhhh  sssssss                         │
╰──────────────────────────────────────────────────────╯
You are P1 (Miss Scarlet) at Lounge  hand: Col. Mustard, Lead Pipe, Mr. Green, Revolver, Wrench
           Notebook           
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Card          ┃ Status     ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ Miss Scarlet  │ ?          │
│ Col. Mustard  │ mine       │
│ Mrs. White    │ ?          │
│ Mr. Green     │ mine       │
│ Mrs. Peacock  │ ?          │
│ Prof. Plum    │ ?          │
│ Candlestick   │ ?          │
│ Dagger        │ held by P2 │
│ Lead Pipe     │ mine       │
│ Revolver      │ mine       │
│ Rope          │ held by P2 │
│ Wrench        │ mine       │
│ Hall          │ ?          │
│ Lounge        │ held by P4 │
│ Dining Room   │ ?          │
│ Kitchen       │ ?          │
│ Ballroom      │ ?          │
│ Conservatory  │ held by P3 │
│ Billiard Room │ ?          │
│ Library       │ ?          │
│ Study         │ ?          │
└───────────────┴────────────┘
Constraints: P3 has one of ['Prof. Plum', 'Revolver', 'Conservatory']; P2 has one of ['Prof. Plum', 
'Candlestick', 'Ballroom']; P2 has one of ['Prof. Plum', 'Rope', 'Billiard Room']; P4 has one of ['Mrs. 
Peacock', 'Revolver', 'Lounge']; P2 has one of ['Mrs. White', 'Dagger', 'Conservatory']
  [0] roll
  [1] passage
  [2] ACCUSE (choose suspect + weapon + room)
Your action #: 0
P1 rolled [5, 1] = 6
╭─ Board (+ = door, X = cellar, S/M/W/G/K/P = tokens) ─╮
│     012345678901234567890123                         │
│  0           .bbbb.                                  │
│  1  kkkkkk....bbbb....cccccc                         │
│  2  kkkkkk..bbbbbbbb..cccccc                         │
│  3  KITCHk..bbbbbbbb..CONSEc                         │
│  4  kkkkkk..BALLROOb..cWGccc                         │
│  5  kkkkkk.+bbbbbbbb+.cccccc                         │
│  6  kkkkkk..bbbbbbbb..+.....                         │
│  7   ...+...bbbbbbbb.......                          │
│  8   ........+....+...iiiiii                         │
│  9  dddddddd.........+iiiiii                         │
│ 10  dddddddd.XXXXXX...BILLIi                         │
│ 11  dddddddd.XXXXXX...iPiiii                         │
│ 12  DINING d+XXXXXX...iiiiii                         │
│ 13  dddddddd.XXXXXX.....+.+                          │
│ 14  dddddddd.XXXXXX..lllllll                         │
│ 15  dddddddd.XXXXXX..lllllll                         │
│ 16   .....+..XXXXXX.+LIBRARl                         │
│ 17  ...........++....lllllll                         │
│ 18   .....+..hhhhhh..lllllll                         │
│ 19  lllllll..hhhhhh.........                         │
│ 20  lllllll.+hhhhhh..+.....                          │
│ 21  LOUNGEl..hHALLh..sssssss                         │
│ 22  lSMKlll..hhhhhh..sSTUDYs                         │
│ 23  lllllll..hhhhhh..sssssss                         │
│ 24  lllllll. hhhhhh  sssssss                         │
╰──────────────────────────────────────────────────────╯
You are P1 (Miss Scarlet) at Lounge  hand: Col. Mustard, Lead Pipe, Mr. Green, Revolver, Wrench
           Notebook           
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Card          ┃ Status     ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ Miss Scarlet  │ ?          │
│ Col. Mustard  │ mine       │
│ Mrs. White    │ ?          │
│ Mr. Green     │ mine       │
│ Mrs. Peacock  │ ?          │
│ Prof. Plum    │ ?          │
│ Candlestick   │ ?          │
│ Dagger        │ held by P2 │
│ Lead Pipe     │ mine       │
│ Revolver      │ mine       │
│ Rope          │ held by P2 │
│ Wrench        │ mine       │
│ Hall          │ ?          │
│ Lounge        │ held by P4 │
│ Dining Room   │ ?          │
│ Kitchen       │ ?          │
│ Ballroom      │ ?          │
│ Conservatory  │ held by P3 │
│ Billiard Room │ ?          │
│ Library       │ ?          │
│ Study         │ ?          │
└───────────────┴────────────┘
Constraints: P3 has one of ['Prof. Plum', 'Revolver', 'Conservatory']; P2 has one of ['Prof. Plum', 
'Candlestick', 'Ballroom']; P2 has one of ['Prof. Plum', 'Rope', 'Billiard Room']; P4 has one of ['Mrs. 
Peacock', 'Revolver', 'Lounge']; P2 has one of ['Mrs. White', 'Dagger', 'Conservatory']
  [0] move to=15,8
  [1] move to=16,3
  [2] move to=17,10
  [3] move to=17,2
  [4] move to=18,1
  [5] move to=21,8
  [6] move to=22,7
  [7] move to=Dining Room
  [8] move to=Hall
  [9] ACCUSE (choose suspect + weapon + room)
Your action #: 8
P1 moved Lounge -> Hall
╭─ Board (+ = door, X = cellar, S/M/W/G/K/P = tokens) ─╮
│     012345678901234567890123                         │
│  0           .bbbb.                                  │
│  1  kkkkkk....bbbb....cccccc                         │
│  2  kkkkkk..bbbbbbbb..cccccc                         │
│  3  KITCHk..bbbbbbbb..CONSEc                         │
│  4  kkkkkk..BALLROOb..cWGccc                         │
│  5  kkkkkk.+bbbbbbbb+.cccccc                         │
│  6  kkkkkk..bbbbbbbb..+.....                         │
│  7   ...+...bbbbbbbb.......                          │
│  8   ........+....+...iiiiii                         │
│  9  dddddddd.........+iiiiii                         │
│ 10  dddddddd.XXXXXX...BILLIi                         │
│ 11  dddddddd.XXXXXX...iPiiii                         │
│ 12  DINING d+XXXXXX...iiiiii                         │
│ 13  dddddddd.XXXXXX.....+.+                          │
│ 14  dddddddd.XXXXXX..lllllll                         │
│ 15  dddddddd.XXXXXX..lllllll                         │
│ 16   .....+..XXXXXX.+LIBRARl                         │
│ 17  ...........++....lllllll                         │
│ 18   .....+..hhhhhh..lllllll                         │
│ 19  lllllll..hhhhhh.........                         │
│ 20  lllllll.+hhhhhh..+.....                          │
│ 21  LOUNGEl..hHALLh..sssssss                         │
│ 22  lMKllll..hShhhh..sSTUDYs                         │
│ 23  lllllll..hhhhhh..sssssss                         │
│ 24  lllllll. hhhhhh  sssssss                         │
╰──────────────────────────────────────────────────────╯
You are P1 (Miss Scarlet) at Hall  hand: Col. Mustard, Lead Pipe, Mr. Green, Revolver, Wrench
           Notebook           
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Card          ┃ Status     ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ Miss Scarlet  │ ?          │
│ Col. Mustard  │ mine       │
│ Mrs. White    │ ?          │
│ Mr. Green     │ mine       │
│ Mrs. Peacock  │ ?          │
│ Prof. Plum    │ ?          │
│ Candlestick   │ ?          │
│ Dagger        │ held by P2 │
│ Lead Pipe     │ mine       │
│ Revolver      │ mine       │
│ Rope          │ held by P2 │
│ Wrench        │ mine       │
│ Hall          │ ?          │
│ Lounge        │ held by P4 │
│ Dining Room   │ ?          │
│ Kitchen       │ ?          │
│ Ballroom      │ ?          │
│ Conservatory  │ held by P3 │
│ Billiard Room │ ?          │
│ Library       │ ?          │
│ Study         │ ?          │
└───────────────┴────────────┘
Constraints: P3 has one of ['Prof. Plum', 'Revolver', 'Conservatory']; P2 has one of ['Prof. Plum', 
'Candlestick', 'Ballroom']; P2 has one of ['Prof. Plum', 'Rope', 'Billiard Room']; P4 has one of ['Mrs. 
Peacock', 'Revolver', 'Lounge']; P2 has one of ['Mrs. White', 'Dagger', 'Conservatory']
  [0] end_turn
  [1] suggest (choose suspect + weapon)
  [2] ACCUSE (choose suspect + weapon + room)
Your action #: 1
  [0] Miss Scarlet
  [1] Col. Mustard
  [2] Mrs. White
  [3] Mr. Green
  [4] Mrs. Peacock
  [5] Prof. Plum
Suspect #: 0
  [0] Candlestick
  [1] Dagger
  [2] Lead Pipe
  [3] Revolver
  [4] Rope
  [5] Wrench
Weapon #: 0
P1 suggests: Miss Scarlet with the Candlestick in the Hall
  P2 cannot disprove
  P3 cannot disprove
  P4 can disprove...
  P4 showed the Miss Scarlet to P1
╭─ Board (+ = door, X = cellar, S/M/W/G/K/P = tokens) ─╮
│     012345678901234567890123                         │
│  0           .bbbb.                                  │
│  1  kkkkkk....bbbb....cccccc                         │
│  2  kkkkkk..bbbbbbbb..cccccc                         │
│  3  KITCHk..bbbbbbbb..CONSEc                         │
│  4  kkkkkk..BALLROOb..cWGccc                         │
│  5  kkkkkk.+bbbbbbbb+.cccccc                         │
│  6  kkkkkk..bbbbbbbb..+.....                         │
│  7   ...+...bbbbbbbb.......                          │
│  8   ........+....+...iiiiii                         │
│  9  dddddddd.........+iiiiii                         │
│ 10  dddddddd.XXXXXX...BILLIi                         │
│ 11  dddddddd.XXXXXX...iPiiii                         │
│ 12  DINING d+XXXXXX...iiiiii                         │
│ 13  dddddddd.XXXXXX.....+.+                          │
│ 14  dddddddd.XXXXXX..lllllll                         │
│ 15  dddddddd.XXXXXX..lllllll                         │
│ 16   .....+..XXXXXX.+LIBRARl                         │
│ 17  ...........++....lllllll                         │
│ 18   .....+..hhhhhh..lllllll                         │
│ 19  lllllll..hhhhhh.........                         │
│ 20  lllllll.+hhhhhh..+.....                          │
│ 21  LOUNGEl..hHALLh..sssssss                         │
│ 22  lMKllll..hShhhh..sSTUDYs                         │
│ 23  lllllll..hhhhhh..sssssss                         │
│ 24  lllllll. hhhhhh  sssssss                         │
╰──────────────────────────────────────────────────────╯
You are P1 (Miss Scarlet) at Hall  hand: Col. Mustard, Lead Pipe, Mr. Green, Revolver, Wrench
           Notebook           
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Card          ┃ Status     ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ Miss Scarlet  │ held by P4 │
│ Col. Mustard  │ mine       │
│ Mrs. White    │ ?          │
│ Mr. Green     │ mine       │
│ Mrs. Peacock  │ ?          │
│ Prof. Plum    │ ?          │
│ Candlestick   │ ?          │
│ Dagger        │ held by P2 │
│ Lead Pipe     │ mine       │
│ Revolver      │ mine       │
│ Rope          │ held by P2 │
│ Wrench        │ mine       │
│ Hall          │ ?          │
│ Lounge        │ held by P4 │
│ Dining Room   │ ?          │
│ Kitchen       │ ?          │
│ Ballroom      │ ?          │
│ Conservatory  │ held by P3 │
│ Billiard Room │ ?          │
│ Library       │ ?          │
│ Study         │ ?          │
└───────────────┴────────────┘
Constraints: P3 has one of ['Prof. Plum', 'Revolver', 'Conservatory']; P2 has one of ['Prof. Plum', 
'Candlestick', 'Ballroom']; P2 has one of ['Prof. Plum', 'Rope', 'Billiard Room']; P4 has one of ['Mrs. 
Peacock', 'Revolver', 'Lounge']; P2 has one of ['Mrs. White', 'Dagger', 'Conservatory']
  [0] end_turn
  [1] ACCUSE (choose suspect + weapon + room)
Your action #: 0
--- Turn 17: P2 ---
P2 rolled [4, 1] = 5
P2 moved Lounge -> Dining Room
P2 suggests: Col. Mustard with the Revolver in the Dining Room
  P3 cannot disprove
  P4 cannot disprove
  P1 can disprove...
P2 suggested Col. Mustard / Revolver / Dining Room. You must show a card.
  [0] Col. Mustard
  [1] Revolver
Show card #: 0
  P1 showed the Col. Mustard to P2
--- Turn 18: P3 ---
P3 suggests: Miss Scarlet with the Dagger in the Conservatory
  P4 can disprove...
  P4 showed a card to P3
--- Turn 19: P4 ---
P4 rolled [5, 3] = 8
P4 moved Conservatory -> Ballroom
P4 suggests: Prof. Plum with the Wrench in the Ballroom
  P1 can disprove...
P4 suggested Prof. Plum / Wrench / Ballroom. You must show a card.
Showing Wrench
  P1 showed the Wrench to P4
--- Turn 20: P1 ---
╭─ Board (+ = door, X = cellar, S/M/W/G/K/P = tokens) ─╮
│     012345678901234567890123                         │
│  0           .bbbb.                                  │
│  1  kkkkkk....bbbb....cccccc                         │
│  2  kkkkkk..bbbbbbbb..cccccc                         │
│  3  KITCHk..bbbbbbbb..CONSEc                         │
│  4  kkkkkk..BALLROOb..cSWccc                         │
│  5  kkkkkk.+bGPbbbbb+.cccccc                         │
│  6  kkkkkk..bbbbbbbb..+.....                         │
│  7   ...+...bbbbbbbb.......                          │
│  8   ........+....+...iiiiii                         │
│  9  dddddddd.........+iiiiii                         │
│ 10  dddddddd.XXXXXX...BILLIi                         │
│ 11  dddddddd.XXXXXX...iiiiii                         │
│ 12  DINING d+XXXXXX...iiiiii                         │
│ 13  dMdddddd.XXXXXX.....+.+                          │
│ 14  dddddddd.XXXXXX..lllllll                         │
│ 15  dddddddd.XXXXXX..lllllll                         │
│ 16   .....+..XXXXXX.+LIBRARl                         │
│ 17  ...........++....lllllll                         │
│ 18   .....+..hhhhhh..lllllll                         │
│ 19  lllllll..hhhhhh.........                         │
│ 20  lllllll.+hhhhhh..+.....                          │
│ 21  LOUNGEl..hHALLh..sssssss                         │
│ 22  lKlllll..hhhhhh..sSTUDYs                         │
│ 23  lllllll..hhhhhh..sssssss                         │
│ 24  lllllll. hhhhhh  sssssss                         │
╰──────────────────────────────────────────────────────╯
You are P1 (Miss Scarlet) at Conservatory  hand: Col. Mustard, Lead Pipe, Mr. Green, Revolver, Wrench
           Notebook           
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Card          ┃ Status     ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ Miss Scarlet  │ held by P4 │
│ Col. Mustard  │ mine       │
│ Mrs. White    │ ?          │
│ Mr. Green     │ mine       │
│ Mrs. Peacock  │ ?          │
│ Prof. Plum    │ ?          │
│ Candlestick   │ ?          │
│ Dagger        │ held by P2 │
│ Lead Pipe     │ mine       │
│ Revolver      │ mine       │
│ Rope          │ held by P2 │
│ Wrench        │ mine       │
│ Hall          │ ?          │
│ Lounge        │ held by P4 │
│ Dining Room   │ ?          │
│ Kitchen       │ ?          │
│ Ballroom      │ ?          │
│ Conservatory  │ held by P3 │
│ Billiard Room │ ?          │
│ Library       │ ?          │
│ Study         │ ?          │
└───────────────┴────────────┘
Constraints: P3 has one of ['Prof. Plum', 'Revolver', 'Conservatory']; P2 has one of ['Prof. Plum', 
'Candlestick', 'Ballroom']; P2 has one of ['Prof. Plum', 'Rope', 'Billiard Room']; P4 has one of ['Mrs. 
Peacock', 'Revolver', 'Lounge']; P2 has one of ['Mrs. White', 'Dagger', 'Conservatory']; P4 has one of ['Miss 
Scarlet', 'Dagger', 'Conservatory']
  [0] roll
  [1] passage
  [2] suggest (choose suspect + weapon)
  [3] ACCUSE (choose suspect + weapon + room)
Your action #: 2
  [0] Miss Scarlet
  [1] Col. Mustard
  [2] Mrs. White
  [3] Mr. Green
  [4] Mrs. Peacock
  [5] Prof. Plum
Suspect #: 4
  [0] Candlestick
  [1] Dagger
  [2] Lead Pipe
  [3] Revolver
  [4] Rope
  [5] Wrench
Weapon #: 0
P1 suggests: Mrs. Peacock with the Candlestick in the Conservatory
  P2 cannot disprove
  P3 can disprove...
  P3 showed the Conservatory to P1
╭─ Board (+ = door, X = cellar, S/M/W/G/K/P = tokens) ─╮
│     012345678901234567890123                         │
│  0           .bbbb.                                  │
│  1  kkkkkk....bbbb....cccccc                         │
│  2  kkkkkk..bbbbbbbb..cccccc                         │
│  3  KITCHk..bbbbbbbb..CONSEc                         │
│  4  kkkkkk..BALLROOb..cSWKcc                         │
│  5  kkkkkk.+bGPbbbbb+.cccccc                         │
│  6  kkkkkk..bbbbbbbb..+.....                         │
│  7   ...+...bbbbbbbb.......                          │
│  8   ........+....+...iiiiii                         │
│  9  dddddddd.........+iiiiii                         │
│ 10  dddddddd.XXXXXX...BILLIi                         │
│ 11  dddddddd.XXXXXX...iiiiii                         │
│ 12  DINING d+XXXXXX...iiiiii                         │
│ 13  dMdddddd.XXXXXX.....+.+                          │
│ 14  dddddddd.XXXXXX..lllllll                         │
│ 15  dddddddd.XXXXXX..lllllll                         │
│ 16   .....+..XXXXXX.+LIBRARl                         │
│ 17  ...........++....lllllll                         │
│ 18   .....+..hhhhhh..lllllll                         │
│ 19  lllllll..hhhhhh.........                         │
│ 20  lllllll.+hhhhhh..+.....                          │
│ 21  LOUNGEl..hHALLh..sssssss                         │
│ 22  lllllll..hhhhhh..sSTUDYs                         │
│ 23  lllllll..hhhhhh..sssssss                         │
│ 24  lllllll. hhhhhh  sssssss                         │
╰──────────────────────────────────────────────────────╯
You are P1 (Miss Scarlet) at Conservatory  hand: Col. Mustard, Lead Pipe, Mr. Green, Revolver, Wrench
           Notebook           
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Card          ┃ Status     ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ Miss Scarlet  │ held by P4 │
│ Col. Mustard  │ mine       │
│ Mrs. White    │ ?          │
│ Mr. Green     │ mine       │
│ Mrs. Peacock  │ ?          │
│ Prof. Plum    │ ?          │
│ Candlestick   │ ?          │
│ Dagger        │ held by P2 │
│ Lead Pipe     │ mine       │
│ Revolver      │ mine       │
│ Rope          │ held by P2 │
│ Wrench        │ mine       │
│ Hall          │ ?          │
│ Lounge        │ held by P4 │
│ Dining Room   │ ?          │
│ Kitchen       │ ?          │
│ Ballroom      │ ?          │
│ Conservatory  │ held by P3 │
│ Billiard Room │ ?          │
│ Library       │ ?          │
│ Study         │ ?          │
└───────────────┴────────────┘
Constraints: P3 has one of ['Prof. Plum', 'Revolver', 'Conservatory']; P2 has one of ['Prof. Plum', 
'Candlestick', 'Ballroom']; P2 has one of ['Prof. Plum', 'Rope', 'Billiard Room']; P4 has one of ['Mrs. 
Peacock', 'Revolver', 'Lounge']; P2 has one of ['Mrs. White', 'Dagger', 'Conservatory']; P4 has one of ['Miss 
Scarlet', 'Dagger', 'Conservatory']
  [0] end_turn
  [1] ACCUSE (choose suspect + weapon + room)
Your action #: 0
--- Turn 21: P2 ---
P2 rolled [6, 5] = 11
P2 moved Dining Room -> Hall
P2 suggests: Prof. Plum with the Candlestick in the Hall
  P3 cannot disprove
  P4 cannot disprove
  P1 cannot disprove
  NOBODY could disprove!
--- Turn 22: P3 ---
P3 took the secret passage Conservatory -> Lounge
P3 suggests: Mrs. Peacock with the Revolver in the Lounge
  P4 can disprove...
  P4 showed a card to P3
--- Turn 23: P4 ---
P4 rolled [3, 5] = 8
P4 moved Ballroom -> Kitchen
P4 suggests: Prof. Plum with the Lead Pipe in the Kitchen
  P1 can disprove...
P4 suggested Prof. Plum / Lead Pipe / Kitchen. You must show a card.
Showing Lead Pipe
  P1 showed the Lead Pipe to P4
--- Turn 24: P1 ---
╭─ Board (+ = door, X = cellar, S/M/W/G/K/P = tokens) ─╮
│     012345678901234567890123                         │
│  0           .bbbb.                                  │
│  1  kkkkkk....bbbb....cccccc                         │
│  2  kkkkkk..bbbbbbbb..cccccc                         │
│  3  KITCHk..bbbbbbbb..CONSEc                         │
│  4  kGPkkk..BALLROOb..cScccc                         │
│  5  kkkkkk.+bbbbbbbb+.cccccc                         │
│  6  kkkkkk..bbbbbbbb..+.....                         │
│  7   ...+...bbbbbbbb.......                          │
│  8   ........+....+...iiiiii                         │
│  9  dddddddd.........+iiiiii                         │
│ 10  dddddddd.XXXXXX...BILLIi                         │
│ 11  dddddddd.XXXXXX...iiiiii                         │
│ 12  DINING d+XXXXXX...iiiiii                         │
│ 13  dddddddd.XXXXXX.....+.+                          │
│ 14  dddddddd.XXXXXX..lllllll                         │
│ 15  dddddddd.XXXXXX..lllllll                         │
│ 16   .....+..XXXXXX.+LIBRARl                         │
│ 17  ...........++....lllllll                         │
│ 18   .....+..hhhhhh..lllllll                         │
│ 19  lllllll..hhhhhh.........                         │
│ 20  lllllll.+hhhhhh..+.....                          │
│ 21  LOUNGEl..hHALLh..sssssss                         │
│ 22  lWKllll..hMhhhh..sSTUDYs                         │
│ 23  lllllll..hhhhhh..sssssss                         │
│ 24  lllllll. hhhhhh  sssssss                         │
╰──────────────────────────────────────────────────────╯
You are P1 (Miss Scarlet) at Conservatory  hand: Col. Mustard, Lead Pipe, Mr. Green, Revolver, Wrench
           Notebook           
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Card          ┃ Status     ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ Miss Scarlet  │ held by P4 │
│ Col. Mustard  │ mine       │
│ Mrs. White    │ ?          │
│ Mr. Green     │ mine       │
│ Mrs. Peacock  │ ?          │
│ Prof. Plum    │ ?          │
│ Candlestick   │ ?          │
│ Dagger        │ held by P2 │
│ Lead Pipe     │ mine       │
│ Revolver      │ mine       │
│ Rope          │ held by P2 │
│ Wrench        │ mine       │
│ Hall          │ ?          │
│ Lounge        │ held by P4 │
│ Dining Room   │ ?          │
│ Kitchen       │ ?          │
│ Ballroom      │ ?          │
│ Conservatory  │ held by P3 │
│ Billiard Room │ ?          │
│ Library       │ ?          │
│ Study         │ ?          │
└───────────────┴────────────┘
Constraints: P2 has one of ['Prof. Plum', 'Candlestick', 'Ballroom']; P2 has one of ['Prof. Plum', 'Rope', 
'Billiard Room']; P4 has one of ['Mrs. Peacock', 'Revolver', 'Lounge']; P2 has one of ['Mrs. White', 'Dagger',
'Conservatory']; P4 has one of ['Miss Scarlet', 'Dagger', 'Conservatory']; P4 has one of ['Mrs. Peacock', 
'Revolver', 'Lounge']
Unrefuted: ['Prof. Plum', 'Candlestick', 'Hall']
  [0] roll
  [1] passage
  [2] ACCUSE (choose suspect + weapon + room)
Your action #: 0
P1 rolled [2, 6] = 8
╭─ Board (+ = door, X = cellar, S/M/W/G/K/P = tokens) ─╮
│     012345678901234567890123                         │
│  0           .bbbb.                                  │
│  1  kkkkkk....bbbb....cccccc                         │
│  2  kkkkkk..bbbbbbbb..cccccc                         │
│  3  KITCHk..bbbbbbbb..CONSEc                         │
│  4  kGPkkk..BALLROOb..cScccc                         │
│  5  kkkkkk.+bbbbbbbb+.cccccc                         │
│  6  kkkkkk..bbbbbbbb..+.....                         │
│  7   ...+...bbbbbbbb.......                          │
│  8   ........+....+...iiiiii                         │
│  9  dddddddd.........+iiiiii                         │
│ 10  dddddddd.XXXXXX...BILLIi                         │
│ 11  dddddddd.XXXXXX...iiiiii                         │
│ 12  DINING d+XXXXXX...iiiiii                         │
│ 13  dddddddd.XXXXXX.....+.+                          │
│ 14  dddddddd.XXXXXX..lllllll                         │
│ 15  dddddddd.XXXXXX..lllllll                         │
│ 16   .....+..XXXXXX.+LIBRARl                         │
│ 17  ...........++....lllllll                         │
│ 18   .....+..hhhhhh..lllllll                         │
│ 19  lllllll..hhhhhh.........                         │
│ 20  lllllll.+hhhhhh..+.....                          │
│ 21  LOUNGEl..hHALLh..sssssss                         │
│ 22  lWKllll..hMhhhh..sSTUDYs                         │
│ 23  lllllll..hhhhhh..sssssss                         │
│ 24  lllllll. hhhhhh  sssssss                         │
╰──────────────────────────────────────────────────────╯
You are P1 (Miss Scarlet) at Conservatory  hand: Col. Mustard, Lead Pipe, Mr. Green, Revolver, Wrench
           Notebook           
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Card          ┃ Status     ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ Miss Scarlet  │ held by P4 │
│ Col. Mustard  │ mine       │
│ Mrs. White    │ ?          │
│ Mr. Green     │ mine       │
│ Mrs. Peacock  │ ?          │
│ Prof. Plum    │ ?          │
│ Candlestick   │ ?          │
│ Dagger        │ held by P2 │
│ Lead Pipe     │ mine       │
│ Revolver      │ mine       │
│ Rope          │ held by P2 │
│ Wrench        │ mine       │
│ Hall          │ ?          │
│ Lounge        │ held by P4 │
│ Dining Room   │ ?          │
│ Kitchen       │ ?          │
│ Ballroom      │ ?          │
│ Conservatory  │ held by P3 │
│ Billiard Room │ ?          │
│ Library       │ ?          │
│ Study         │ ?          │
└───────────────┴────────────┘
Constraints: P2 has one of ['Prof. Plum', 'Candlestick', 'Ballroom']; P2 has one of ['Prof. Plum', 'Rope', 
'Billiard Room']; P4 has one of ['Mrs. Peacock', 'Revolver', 'Lounge']; P2 has one of ['Mrs. White', 'Dagger',
'Conservatory']; P4 has one of ['Miss Scarlet', 'Dagger', 'Conservatory']; P4 has one of ['Mrs. Peacock', 
'Revolver', 'Lounge']
Unrefuted: ['Prof. Plum', 'Candlestick', 'Hall']
  [0] move to=1,16
  [1] move to=10,15
  [2] move to=11,16
  [3] move to=12,17
  [4] move to=8,13
  [5] move to=9,14
  [6] move to=Ballroom
  [7] move to=Billiard Room
  [8] ACCUSE (choose suspect + weapon + room)
Your action #: 6
P1 moved Conservatory -> Ballroom
╭─ Board (+ = door, X = cellar, S/M/W/G/K/P = tokens) ─╮
│     012345678901234567890123                         │
│  0           .bbbb.                                  │
│  1  kkkkkk....bbbb....cccccc                         │
│  2  kkkkkk..bbbbbbbb..cccccc                         │
│  3  KITCHk..bbbbbbbb..CONSEc                         │
│  4  kGPkkk..BALLROOb..cccccc                         │
│  5  kkkkkk.+bSbbbbbb+.cccccc                         │
│  6  kkkkkk..bbbbbbbb..+.....                         │
│  7   ...+...bbbbbbbb.......                          │
│  8   ........+....+...iiiiii                         │
│  9  dddddddd.........+iiiiii                         │
│ 10  dddddddd.XXXXXX...BILLIi                         │
│ 11  dddddddd.XXXXXX...iiiiii                         │
│ 12  DINING d+XXXXXX...iiiiii                         │
│ 13  dddddddd.XXXXXX.....+.+                          │
│ 14  dddddddd.XXXXXX..lllllll                         │
│ 15  dddddddd.XXXXXX..lllllll                         │
│ 16   .....+..XXXXXX.+LIBRARl                         │
│ 17  ...........++....lllllll                         │
│ 18   .....+..hhhhhh..lllllll                         │
│ 19  lllllll..hhhhhh.........                         │
│ 20  lllllll.+hhhhhh..+.....                          │
│ 21  LOUNGEl..hHALLh..sssssss                         │
│ 22  lWKllll..hMhhhh..sSTUDYs                         │
│ 23  lllllll..hhhhhh..sssssss                         │
│ 24  lllllll. hhhhhh  sssssss                         │
╰──────────────────────────────────────────────────────╯
You are P1 (Miss Scarlet) at Ballroom  hand: Col. Mustard, Lead Pipe, Mr. Green, Revolver, Wrench
           Notebook           
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Card          ┃ Status     ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ Miss Scarlet  │ held by P4 │
│ Col. Mustard  │ mine       │
│ Mrs. White    │ ?          │
│ Mr. Green     │ mine       │
│ Mrs. Peacock  │ ?          │
│ Prof. Plum    │ ?          │
│ Candlestick   │ ?          │
│ Dagger        │ held by P2 │
│ Lead Pipe     │ mine       │
│ Revolver      │ mine       │
│ Rope          │ held by P2 │
│ Wrench        │ mine       │
│ Hall          │ ?          │
│ Lounge        │ held by P4 │
│ Dining Room   │ ?          │
│ Kitchen       │ ?          │
│ Ballroom      │ ?          │
│ Conservatory  │ held by P3 │
│ Billiard Room │ ?          │
│ Library       │ ?          │
│ Study         │ ?          │
└───────────────┴────────────┘
Constraints: P2 has one of ['Prof. Plum', 'Candlestick', 'Ballroom']; P2 has one of ['Prof. Plum', 'Rope', 
'Billiard Room']; P4 has one of ['Mrs. Peacock', 'Revolver', 'Lounge']; P2 has one of ['Mrs. White', 'Dagger',
'Conservatory']; P4 has one of ['Miss Scarlet', 'Dagger', 'Conservatory']; P4 has one of ['Mrs. Peacock', 
'Revolver', 'Lounge']
Unrefuted: ['Prof. Plum', 'Candlestick', 'Hall']
  [0] end_turn
  [1] suggest (choose suspect + weapon)
  [2] ACCUSE (choose suspect + weapon + room)
Your action #: 1
  [0] Miss Scarlet
  [1] Col. Mustard
  [2] Mrs. White
  [3] Mr. Green
  [4] Mrs. Peacock
  [5] Prof. Plum
Suspect #: 2
  [0] Candlestick
  [1] Dagger
  [2] Lead Pipe
  [3] Revolver
  [4] Rope
  [5] Wrench
Weapon #: 0
P1 suggests: Mrs. White with the Candlestick in the Ballroom
  P2 can disprove...
  P2 showed the Ballroom to P1
╭─ Board (+ = door, X = cellar, S/M/W/G/K/P = tokens) ─╮
│     012345678901234567890123                         │
│  0           .bbbb.                                  │
│  1  kkkkkk....bbbb....cccccc                         │
│  2  kkkkkk..bbbbbbbb..cccccc                         │
│  3  KITCHk..bbbbbbbb..CONSEc                         │
│  4  kGPkkk..BALLROOb..cccccc                         │
│  5  kkkkkk.+bSWbbbbb+.cccccc                         │
│  6  kkkkkk..bbbbbbbb..+.....                         │
│  7   ...+...bbbbbbbb.......                          │
│  8   ........+....+...iiiiii                         │
│  9  dddddddd.........+iiiiii                         │
│ 10  dddddddd.XXXXXX...BILLIi                         │
│ 11  dddddddd.XXXXXX...iiiiii                         │
│ 12  DINING d+XXXXXX...iiiiii                         │
│ 13  dddddddd.XXXXXX.....+.+                          │
│ 14  dddddddd.XXXXXX..lllllll                         │
│ 15  dddddddd.XXXXXX..lllllll                         │
│ 16   .....+..XXXXXX.+LIBRARl                         │
│ 17  ...........++....lllllll                         │
│ 18   .....+..hhhhhh..lllllll                         │
│ 19  lllllll..hhhhhh.........                         │
│ 20  lllllll.+hhhhhh..+.....                          │
│ 21  LOUNGEl..hHALLh..sssssss                         │
│ 22  lKlllll..hMhhhh..sSTUDYs                         │
│ 23  lllllll..hhhhhh..sssssss                         │
│ 24  lllllll. hhhhhh  sssssss                         │
╰──────────────────────────────────────────────────────╯
You are P1 (Miss Scarlet) at Ballroom  hand: Col. Mustard, Lead Pipe, Mr. Green, Revolver, Wrench
           Notebook           
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Card          ┃ Status     ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ Miss Scarlet  │ held by P4 │
│ Col. Mustard  │ mine       │
│ Mrs. White    │ ?          │
│ Mr. Green     │ mine       │
│ Mrs. Peacock  │ ?          │
│ Prof. Plum    │ ?          │
│ Candlestick   │ ?          │
│ Dagger        │ held by P2 │
│ Lead Pipe     │ mine       │
│ Revolver      │ mine       │
│ Rope          │ held by P2 │
│ Wrench        │ mine       │
│ Hall          │ ?          │
│ Lounge        │ held by P4 │
│ Dining Room   │ ?          │
│ Kitchen       │ ?          │
│ Ballroom      │ held by P2 │
│ Conservatory  │ held by P3 │
│ Billiard Room │ ?          │
│ Library       │ ?          │
│ Study         │ ?          │
└───────────────┴────────────┘
Constraints: P2 has one of ['Prof. Plum', 'Candlestick', 'Ballroom']; P2 has one of ['Prof. Plum', 'Rope', 
'Billiard Room']; P4 has one of ['Mrs. Peacock', 'Revolver', 'Lounge']; P2 has one of ['Mrs. White', 'Dagger',
'Conservatory']; P4 has one of ['Miss Scarlet', 'Dagger', 'Conservatory']; P4 has one of ['Mrs. Peacock', 
'Revolver', 'Lounge']
Unrefuted: ['Prof. Plum', 'Candlestick', 'Hall']
  [0] end_turn
  [1] ACCUSE (choose suspect + weapon + room)
Your action #: 0
--- Turn 25: P2 ---
P2 rolled [1, 1] = 2
P2 moved Hall -> 17,10
--- Turn 26: P3 ---
P3 suggests: Mrs. Peacock with the Revolver in the Ballroom
  P4 can disprove...
  P4 showed a card to P3
--- Turn 27: P4 ---
P4 took the secret passage Kitchen -> Study
P4 suggests: Prof. Plum with the Candlestick in the Study
  P1 cannot disprove
  P2 cannot disprove
  P3 can disprove...
  P3 showed a card to P4
--- Turn 28: P1 ---
╭─ Board (+ = door, X = cellar, S/M/W/G/K/P = tokens) ─╮
│     012345678901234567890123                         │
│  0           .bbbb.                                  │
│  1  kkkkkk....bbbb....cccccc                         │
│  2  kkkkkk..bbbbbbbb..cccccc                         │
│  3  KITCHk..bbbbbbbb..CONSEc                         │
│  4  kkkkkk..BALLROOb..cccccc                         │
│  5  kkkkkk.+bSWKbbbb+.cccccc                         │
│  6  kkkkkk..bbbbbbbb..+.....                         │
│  7   ...+...bbbbbbbb.......                          │
│  8   ........+....+...iiiiii                         │
│  9  dddddddd.........+iiiiii                         │
│ 10  dddddddd.XXXXXX...BILLIi                         │
│ 11  dddddddd.XXXXXX...iiiiii                         │
│ 12  DINING d+XXXXXX...iiiiii                         │
│ 13  dddddddd.XXXXXX.....+.+                          │
│ 14  dddddddd.XXXXXX..lllllll                         │
│ 15  dddddddd.XXXXXX..lllllll                         │
│ 16   .....+..XXXXXX.+LIBRARl                         │
│ 17  ..........M++....lllllll                         │
│ 18   .....+..hhhhhh..lllllll                         │
│ 19  lllllll..hhhhhh.........                         │
│ 20  lllllll.+hhhhhh..+.....                          │
│ 21  LOUNGEl..hHALLh..sssssss                         │
│ 22  lllllll..hhhhhh..sSTUDYs                         │
│ 23  lllllll..hhhhhh..sGPssss                         │
│ 24  lllllll. hhhhhh  sssssss                         │
╰──────────────────────────────────────────────────────╯
You are P1 (Miss Scarlet) at Ballroom  hand: Col. Mustard, Lead Pipe, Mr. Green, Revolver, Wrench
           Notebook           
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Card          ┃ Status     ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ Miss Scarlet  │ held by P4 │
│ Col. Mustard  │ mine       │
│ Mrs. White    │ ?          │
│ Mr. Green     │ mine       │
│ Mrs. Peacock  │ ?          │
│ Prof. Plum    │ ?          │
│ Candlestick   │ ?          │
│ Dagger        │ held by P2 │
│ Lead Pipe     │ mine       │
│ Revolver      │ mine       │
│ Rope          │ held by P2 │
│ Wrench        │ mine       │
│ Hall          │ ?          │
│ Lounge        │ held by P4 │
│ Dining Room   │ ?          │
│ Kitchen       │ ?          │
│ Ballroom      │ held by P2 │
│ Conservatory  │ held by P3 │
│ Billiard Room │ ?          │
│ Library       │ ?          │
│ Study         │ ?          │
└───────────────┴────────────┘
Constraints: P4 has one of ['Mrs. Peacock', 'Revolver', 'Lounge']; P2 has one of ['Mrs. White', 'Dagger', 
'Conservatory']; P4 has one of ['Miss Scarlet', 'Dagger', 'Conservatory']; P4 has one of ['Mrs. Peacock', 
'Revolver', 'Lounge']; P4 has one of ['Mrs. Peacock', 'Revolver', 'Ballroom']; P3 has one of ['Prof. Plum', 
'Candlestick', 'Study']
Unrefuted: ['Prof. Plum', 'Candlestick', 'Hall']
  [0] roll
  [1] ACCUSE (choose suspect + weapon + room)
Your action #: 0
P1 rolled [6, 2] = 8
╭─ Board (+ = door, X = cellar, S/M/W/G/K/P = tokens) ─╮
│     012345678901234567890123                         │
│  0           .bbbb.                                  │
│  1  kkkkkk....bbbb....cccccc                         │
│  2  kkkkkk..bbbbbbbb..cccccc                         │
│  3  KITCHk..bbbbbbbb..CONSEc                         │
│  4  kkkkkk..BALLROOb..cccccc                         │
│  5  kkkkkk.+bSWKbbbb+.cccccc                         │
│  6  kkkkkk..bbbbbbbb..+.....                         │
│  7   ...+...bbbbbbbb.......                          │
│  8   ........+....+...iiiiii                         │
│  9  dddddddd.........+iiiiii                         │
│ 10  dddddddd.XXXXXX...BILLIi                         │
│ 11  dddddddd.XXXXXX...iiiiii                         │
│ 12  DINING d+XXXXXX...iiiiii                         │
│ 13  dddddddd.XXXXXX.....+.+                          │
│ 14  dddddddd.XXXXXX..lllllll                         │
│ 15  dddddddd.XXXXXX..lllllll                         │
│ 16   .....+..XXXXXX.+LIBRARl                         │
│ 17  ..........M++....lllllll                         │
│ 18   .....+..hhhhhh..lllllll                         │
│ 19  lllllll..hhhhhh.........                         │
│ 20  lllllll.+hhhhhh..+.....                          │
│ 21  LOUNGEl..hHALLh..sssssss                         │
│ 22  lllllll..hhhhhh..sSTUDYs                         │
│ 23  lllllll..hhhhhh..sGPssss                         │
│ 24  lllllll. hhhhhh  sssssss                         │
╰──────────────────────────────────────────────────────╯
You are P1 (Miss Scarlet) at Ballroom  hand: Col. Mustard, Lead Pipe, Mr. Green, Revolver, Wrench
           Notebook           
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Card          ┃ Status     ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ Miss Scarlet  │ held by P4 │
│ Col. Mustard  │ mine       │
│ Mrs. White    │ ?          │
│ Mr. Green     │ mine       │
│ Mrs. Peacock  │ ?          │
│ Prof. Plum    │ ?          │
│ Candlestick   │ ?          │
│ Dagger        │ held by P2 │
│ Lead Pipe     │ mine       │
│ Revolver      │ mine       │
│ Rope          │ held by P2 │
│ Wrench        │ mine       │
│ Hall          │ ?          │
│ Lounge        │ held by P4 │
│ Dining Room   │ ?          │
│ Kitchen       │ ?          │
│ Ballroom      │ held by P2 │
│ Conservatory  │ held by P3 │
│ Billiard Room │ ?          │
│ Library       │ ?          │
│ Study         │ ?          │
└───────────────┴────────────┘
Constraints: P4 has one of ['Mrs. Peacock', 'Revolver', 'Lounge']; P2 has one of ['Mrs. White', 'Dagger', 
'Conservatory']; P4 has one of ['Miss Scarlet', 'Dagger', 'Conservatory']; P4 has one of ['Mrs. Peacock', 
'Revolver', 'Lounge']; P4 has one of ['Mrs. Peacock', 'Revolver', 'Ballroom']; P3 has one of ['Prof. Plum', 
'Candlestick', 'Study']
Unrefuted: ['Prof. Plum', 'Candlestick', 'Hall']
  [0] move to=0,14
  [1] move to=0,9
  [2] move to=12,17
  [3] move to=13,16
  [4] move to=14,15
  [5] move to=14,8
  [6] move to=6,22
  [7] move to=7,2
  [8] move to=7,21
  [9] move to=8,2
  [10] move to=Billiard Room
  [11] move to=Conservatory
  [12] move to=Dining Room
  [13] move to=Kitchen
  [14] ACCUSE (choose suspect + weapon + room)
Your action #: 12
P1 moved Ballroom -> Dining Room
╭─ Board (+ = door, X = cellar, S/M/W/G/K/P = tokens) ─╮
│     012345678901234567890123                         │
│  0           .bbbb.                                  │
│  1  kkkkkk....bbbb....cccccc                         │
│  2  kkkkkk..bbbbbbbb..cccccc                         │
│  3  KITCHk..bbbbbbbb..CONSEc                         │
│  4  kkkkkk..BALLROOb..cccccc                         │
│  5  kkkkkk.+bWKbbbbb+.cccccc                         │
│  6  kkkkkk..bbbbbbbb..+.....                         │
│  7   ...+...bbbbbbbb.......                          │
│  8   ........+....+...iiiiii                         │
│  9  dddddddd.........+iiiiii                         │
│ 10  dddddddd.XXXXXX...BILLIi                         │
│ 11  dddddddd.XXXXXX...iiiiii                         │
│ 12  DINING d+XXXXXX...iiiiii                         │
│ 13  dSdddddd.XXXXXX.....+.+                          │
│ 14  dddddddd.XXXXXX..lllllll                         │
│ 15  dddddddd.XXXXXX..lllllll                         │
│ 16   .....+..XXXXXX.+LIBRARl                         │
│ 17  ..........M++....lllllll                         │
│ 18   .....+..hhhhhh..lllllll                         │
│ 19  lllllll..hhhhhh.........                         │
│ 20  lllllll.+hhhhhh..+.....                          │
│ 21  LOUNGEl..hHALLh..sssssss                         │
│ 22  lllllll..hhhhhh..sSTUDYs                         │
│ 23  lllllll..hhhhhh..sGPssss                         │
│ 24  lllllll. hhhhhh  sssssss                         │
╰──────────────────────────────────────────────────────╯
You are P1 (Miss Scarlet) at Dining Room  hand: Col. Mustard, Lead Pipe, Mr. Green, Revolver, Wrench
           Notebook           
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Card          ┃ Status     ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ Miss Scarlet  │ held by P4 │
│ Col. Mustard  │ mine       │
│ Mrs. White    │ ?          │
│ Mr. Green     │ mine       │
│ Mrs. Peacock  │ ?          │
│ Prof. Plum    │ ?          │
│ Candlestick   │ ?          │
│ Dagger        │ held by P2 │
│ Lead Pipe     │ mine       │
│ Revolver      │ mine       │
│ Rope          │ held by P2 │
│ Wrench        │ mine       │
│ Hall          │ ?          │
│ Lounge        │ held by P4 │
│ Dining Room   │ ?          │
│ Kitchen       │ ?          │
│ Ballroom      │ held by P2 │
│ Conservatory  │ held by P3 │
│ Billiard Room │ ?          │
│ Library       │ ?          │
│ Study         │ ?          │
└───────────────┴────────────┘
Constraints: P4 has one of ['Mrs. Peacock', 'Revolver', 'Lounge']; P2 has one of ['Mrs. White', 'Dagger', 
'Conservatory']; P4 has one of ['Miss Scarlet', 'Dagger', 'Conservatory']; P4 has one of ['Mrs. Peacock', 
'Revolver', 'Lounge']; P4 has one of ['Mrs. Peacock', 'Revolver', 'Ballroom']; P3 has one of ['Prof. Plum', 
'Candlestick', 'Study']
Unrefuted: ['Prof. Plum', 'Candlestick', 'Hall']
  [0] end_turn
  [1] suggest (choose suspect + weapon)
  [2] ACCUSE (choose suspect + weapon + room)
Your action #: 1
  [0] Miss Scarlet
  [1] Col. Mustard
  [2] Mrs. White
  [3] Mr. Green
  [4] Mrs. Peacock
  [5] Prof. Plum
Suspect #: 2
  [0] Candlestick
  [1] Dagger
  [2] Lead Pipe
  [3] Revolver
  [4] Rope
  [5] Wrench
Weapon #: 0
P1 suggests: Mrs. White with the Candlestick in the Dining Room
  P2 can disprove...
  P2 showed the Dining Room to P1
╭─ Board (+ = door, X = cellar, S/M/W/G/K/P = tokens) ─╮
│     012345678901234567890123                         │
│  0           .bbbb.                                  │
│  1  kkkkkk....bbbb....cccccc                         │
│  2  kkkkkk..bbbbbbbb..cccccc                         │
│  3  KITCHk..bbbbbbbb..CONSEc                         │
│  4  kkkkkk..BALLROOb..cccccc                         │
│  5  kkkkkk.+bKbbbbbb+.cccccc                         │
│  6  kkkkkk..bbbbbbbb..+.....                         │
│  7   ...+...bbbbbbbb.......                          │
│  8   ........+....+...iiiiii                         │
│  9  dddddddd.........+iiiiii                         │
│ 10  dddddddd.XXXXXX...BILLIi                         │
│ 11  dddddddd.XXXXXX...iiiiii                         │
│ 12  DINING d+XXXXXX...iiiiii                         │
│ 13  dSWddddd.XXXXXX.....+.+                          │
│ 14  dddddddd.XXXXXX..lllllll                         │
│ 15  dddddddd.XXXXXX..lllllll                         │
│ 16   .....+..XXXXXX.+LIBRARl                         │
│ 17  ..........M++....lllllll                         │
│ 18   .....+..hhhhhh..lllllll                         │
│ 19  lllllll..hhhhhh.........                         │
│ 20  lllllll.+hhhhhh..+.....                          │
│ 21  LOUNGEl..hHALLh..sssssss                         │
│ 22  lllllll..hhhhhh..sSTUDYs                         │
│ 23  lllllll..hhhhhh..sGPssss                         │
│ 24  lllllll. hhhhhh  sssssss                         │
╰──────────────────────────────────────────────────────╯
You are P1 (Miss Scarlet) at Dining Room  hand: Col. Mustard, Lead Pipe, Mr. Green, Revolver, Wrench
           Notebook           
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Card          ┃ Status     ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ Miss Scarlet  │ held by P4 │
│ Col. Mustard  │ mine       │
│ Mrs. White    │ ?          │
│ Mr. Green     │ mine       │
│ Mrs. Peacock  │ ?          │
│ Prof. Plum    │ ?          │
│ Candlestick   │ ?          │
│ Dagger        │ held by P2 │
│ Lead Pipe     │ mine       │
│ Revolver      │ mine       │
│ Rope          │ held by P2 │
│ Wrench        │ mine       │
│ Hall          │ ?          │
│ Lounge        │ held by P4 │
│ Dining Room   │ held by P2 │
│ Kitchen       │ ?          │
│ Ballroom      │ held by P2 │
│ Conservatory  │ held by P3 │
│ Billiard Room │ ?          │
│ Library       │ ?          │
│ Study         │ ?          │
└───────────────┴────────────┘
Constraints: P4 has one of ['Mrs. Peacock', 'Revolver', 'Lounge']; P2 has one of ['Mrs. White', 'Dagger', 
'Conservatory']; P4 has one of ['Miss Scarlet', 'Dagger', 'Conservatory']; P4 has one of ['Mrs. Peacock', 
'Revolver', 'Lounge']; P4 has one of ['Mrs. Peacock', 'Revolver', 'Ballroom']; P3 has one of ['Prof. Plum', 
'Candlestick', 'Study']
Unrefuted: ['Prof. Plum', 'Candlestick', 'Hall']
  [0] end_turn
  [1] ACCUSE (choose suspect + weapon + room)
Your action #: 0
--- Turn 29: P2 ---
P2 rolled [3, 1] = 4
P2 moved 17,10 -> Hall
P2 suggests: Miss Scarlet with the Wrench in the Hall
  P3 cannot disprove
  P4 can disprove...
  P4 showed a card to P2
--- Turn 30: P3 ---
P3 suggests: Prof. Plum with the Wrench in the Dining Room
  P4 cannot disprove
  P1 can disprove...
P3 suggested Prof. Plum / Wrench / Dining Room. You must show a card.
Showing Wrench
  P1 showed the Wrench to P3
--- Turn 31: P4 ---
P4 took the secret passage Study -> Kitchen
P4 suggests: Mrs. White with the Candlestick in the Kitchen
  P1 cannot disprove
  P2 can disprove...
  P2 showed a card to P4
--- Turn 32: P1 ---
╭─ Board (+ = door, X = cellar, S/M/W/G/K/P = tokens) ─╮
│     012345678901234567890123                         │
│  0           .bbbb.                                  │
│  1  kkkkkk....bbbb....cccccc                         │
│  2  kkkkkk..bbbbbbbb..cccccc                         │
│  3  KITCHk..bbbbbbbb..CONSEc                         │
│  4  kWGkkk..BALLROOb..cccccc                         │
│  5  kkkkkk.+bKbbbbbb+.cccccc                         │
│  6  kkkkkk..bbbbbbbb..+.....                         │
│  7   ...+...bbbbbbbb.......                          │
│  8   ........+....+...iiiiii                         │
│  9  dddddddd.........+iiiiii                         │
│ 10  dddddddd.XXXXXX...BILLIi                         │
│ 11  dddddddd.XXXXXX...iiiiii                         │
│ 12  DINING d+XXXXXX...iiiiii                         │
│ 13  dPdddddd.XXXXXX.....+.+                          │
│ 14  dddddddd.XXXXXX..lllllll                         │
│ 15  dddddddd.XXXXXX..lllllll                         │
│ 16   .....+..XXXXXX.+LIBRARl                         │
│ 17  ...........++....lllllll                         │
│ 18   .....+..hhhhhh..lllllll                         │
│ 19  lllllll..hhhhhh.........                         │
│ 20  lllllll.+hhhhhh..+.....                          │
│ 21  LOUNGEl..hHALLh..sssssss                         │
│ 22  lllllll..hSMhhh..sSTUDYs                         │
│ 23  lllllll..hhhhhh..sssssss                         │
│ 24  lllllll. hhhhhh  sssssss                         │
╰──────────────────────────────────────────────────────╯
You are P1 (Miss Scarlet) at Hall  hand: Col. Mustard, Lead Pipe, Mr. Green, Revolver, Wrench
           Notebook           
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Card          ┃ Status     ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ Miss Scarlet  │ held by P4 │
│ Col. Mustard  │ mine       │
│ Mrs. White    │ ?          │
│ Mr. Green     │ mine       │
│ Mrs. Peacock  │ ?          │
│ Prof. Plum    │ ?          │
│ Candlestick   │ ?          │
│ Dagger        │ held by P2 │
│ Lead Pipe     │ mine       │
│ Revolver      │ mine       │
│ Rope          │ held by P2 │
│ Wrench        │ mine       │
│ Hall          │ ?          │
│ Lounge        │ held by P4 │
│ Dining Room   │ held by P2 │
│ Kitchen       │ ?          │
│ Ballroom      │ held by P2 │
│ Conservatory  │ held by P3 │
│ Billiard Room │ ?          │
│ Library       │ ?          │
│ Study         │ ?          │
└───────────────┴────────────┘
Constraints: P4 has one of ['Miss Scarlet', 'Dagger', 'Conservatory']; P4 has one of ['Mrs. Peacock', 
'Revolver', 'Lounge']; P4 has one of ['Mrs. Peacock', 'Revolver', 'Ballroom']; P3 has one of ['Prof. Plum', 
'Candlestick', 'Study']; P4 has one of ['Miss Scarlet', 'Wrench', 'Hall']; P2 has one of ['Mrs. White', 
'Candlestick', 'Kitchen']
Unrefuted: ['Prof. Plum', 'Candlestick', 'Hall']
  [0] roll
  [1] suggest (choose suspect + weapon)
  [2] ACCUSE (choose suspect + weapon + room)
Your action #: 1
  [0] Miss Scarlet
  [1] Col. Mustard
  [2] Mrs. White
  [3] Mr. Green
  [4] Mrs. Peacock
  [5] Prof. Plum
Suspect #: 2
  [0] Candlestick
  [1] Dagger
  [2] Lead Pipe
  [3] Revolver
  [4] Rope
  [5] Wrench
Weapon #: 0
P1 suggests: Mrs. White with the Candlestick in the Hall
  P2 cannot disprove
  P3 can disprove...
  P3 showed the Mrs. White to P1
╭─ Board (+ = door, X = cellar, S/M/W/G/K/P = tokens) ─╮
│     012345678901234567890123                         │
│  0           .bbbb.                                  │
│  1  kkkkkk....bbbb....cccccc                         │
│  2  kkkkkk..bbbbbbbb..cccccc                         │
│  3  KITCHk..bbbbbbbb..CONSEc                         │
│  4  kGkkkk..BALLROOb..cccccc                         │
│  5  kkkkkk.+bKbbbbbb+.cccccc                         │
│  6  kkkkkk..bbbbbbbb..+.....                         │
│  7   ...+...bbbbbbbb.......                          │
│  8   ........+....+...iiiiii                         │
│  9  dddddddd.........+iiiiii                         │
│ 10  dddddddd.XXXXXX...BILLIi                         │
│ 11  dddddddd.XXXXXX...iiiiii                         │
│ 12  DINING d+XXXXXX...iiiiii                         │
│ 13  dPdddddd.XXXXXX.....+.+                          │
│ 14  dddddddd.XXXXXX..lllllll                         │
│ 15  dddddddd.XXXXXX..lllllll                         │
│ 16   .....+..XXXXXX.+LIBRARl                         │
│ 17  ...........++....lllllll                         │
│ 18   .....+..hhhhhh..lllllll                         │
│ 19  lllllll..hhhhhh.........                         │
│ 20  lllllll.+hhhhhh..+.....                          │
│ 21  LOUNGEl..hHALLh..sssssss                         │
│ 22  lllllll..hSMWhh..sSTUDYs                         │
│ 23  lllllll..hhhhhh..sssssss                         │
│ 24  lllllll. hhhhhh  sssssss                         │
╰──────────────────────────────────────────────────────╯
You are P1 (Miss Scarlet) at Hall  hand: Col. Mustard, Lead Pipe, Mr. Green, Revolver, Wrench
           Notebook           
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Card          ┃ Status     ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ Miss Scarlet  │ held by P4 │
│ Col. Mustard  │ mine       │
│ Mrs. White    │ held by P3 │
│ Mr. Green     │ mine       │
│ Mrs. Peacock  │ ?          │
│ Prof. Plum    │ ?          │
│ Candlestick   │ ?          │
│ Dagger        │ held by P2 │
│ Lead Pipe     │ mine       │
│ Revolver      │ mine       │
│ Rope          │ held by P2 │
│ Wrench        │ mine       │
│ Hall          │ ?          │
│ Lounge        │ held by P4 │
│ Dining Room   │ held by P2 │
│ Kitchen       │ ?          │
│ Ballroom      │ held by P2 │
│ Conservatory  │ held by P3 │
│ Billiard Room │ ?          │
│ Library       │ ?          │
│ Study         │ ?          │
└───────────────┴────────────┘
Constraints: P4 has one of ['Miss Scarlet', 'Dagger', 'Conservatory']; P4 has one of ['Mrs. Peacock', 
'Revolver', 'Lounge']; P4 has one of ['Mrs. Peacock', 'Revolver', 'Ballroom']; P3 has one of ['Prof. Plum', 
'Candlestick', 'Study']; P4 has one of ['Miss Scarlet', 'Wrench', 'Hall']; P2 has one of ['Mrs. White', 
'Candlestick', 'Kitchen']
Unrefuted: ['Prof. Plum', 'Candlestick', 'Hall']
  [0] end_turn
  [1] ACCUSE (choose suspect + weapon + room)
Your action #: 0
--- Turn 33: P2 ---
P2 rolled [2, 1] = 3
P2 moved Hall -> 17,14
--- Turn 34: P3 ---
P3 suggests: Prof. Plum with the Lead Pipe in the Hall
  P4 cannot disprove
  P1 can disprove...
P3 suggested Prof. Plum / Lead Pipe / Hall. You must show a card.
Showing Lead Pipe
  P1 showed the Lead Pipe to P3
--- Turn 35: P4 ---
P4 rolled [4, 3] = 7
P4 moved Kitchen -> Ballroom
P4 suggests: Mr. Green with the Candlestick in the Ballroom
  P1 can disprove...
P4 suggested Mr. Green / Candlestick / Ballroom. You must show a card.
Showing Mr. Green
  P1 showed the Mr. Green to P4
--- Turn 36: P1 ---
╭─ Board (+ = door, X = cellar, S/M/W/G/K/P = tokens) ─╮
│     012345678901234567890123                         │
│  0           .bbbb.                                  │
│  1  kkkkkk....bbbb....cccccc                         │
│  2  kkkkkk..bbbbbbbb..cccccc                         │
│  3  KITCHk..bbbbbbbb..CONSEc                         │
│  4  kkkkkk..BALLROOb..cccccc                         │
│  5  kkkkkk.+bGKbbbbb+.cccccc                         │
│  6  kkkkkk..bbbbbbbb..+.....                         │
│  7   ...+...bbbbbbbb.......                          │
│  8   ........+....+...iiiiii                         │
│  9  dddddddd.........+iiiiii                         │
│ 10  dddddddd.XXXXXX...BILLIi                         │
│ 11  dddddddd.XXXXXX...iiiiii                         │
│ 12  DINING d+XXXXXX...iiiiii                         │
│ 13  dddddddd.XXXXXX.....+.+                          │
│ 14  dddddddd.XXXXXX..lllllll                         │
│ 15  dddddddd.XXXXXX..lllllll                         │
│ 16   .....+..XXXXXX.+LIBRARl                         │
│ 17  ...........++.M..lllllll                         │
│ 18   .....+..hhhhhh..lllllll                         │
│ 19  lllllll..hhhhhh.........                         │
│ 20  lllllll.+hhhhhh..+.....                          │
│ 21  LOUNGEl..hHALLh..sssssss                         │
│ 22  lllllll..hSWPhh..sSTUDYs                         │
│ 23  lllllll..hhhhhh..sssssss                         │
│ 24  lllllll. hhhhhh  sssssss                         │
╰──────────────────────────────────────────────────────╯
You are P1 (Miss Scarlet) at Hall  hand: Col. Mustard, Lead Pipe, Mr. Green, Revolver, Wrench
           Notebook           
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Card          ┃ Status     ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ Miss Scarlet  │ held by P4 │
│ Col. Mustard  │ mine       │
│ Mrs. White    │ held by P3 │
│ Mr. Green     │ mine       │
│ Mrs. Peacock  │ ?          │
│ Prof. Plum    │ ?          │
│ Candlestick   │ ?          │
│ Dagger        │ held by P2 │
│ Lead Pipe     │ mine       │
│ Revolver      │ mine       │
│ Rope          │ held by P2 │
│ Wrench        │ mine       │
│ Hall          │ ?          │
│ Lounge        │ held by P4 │
│ Dining Room   │ held by P2 │
│ Kitchen       │ ?          │
│ Ballroom      │ held by P2 │
│ Conservatory  │ held by P3 │
│ Billiard Room │ ?          │
│ Library       │ ?          │
│ Study         │ ?          │
└───────────────┴────────────┘
Constraints: P4 has one of ['Miss Scarlet', 'Dagger', 'Conservatory']; P4 has one of ['Mrs. Peacock', 
'Revolver', 'Lounge']; P4 has one of ['Mrs. Peacock', 'Revolver', 'Ballroom']; P3 has one of ['Prof. Plum', 
'Candlestick', 'Study']; P4 has one of ['Miss Scarlet', 'Wrench', 'Hall']; P2 has one of ['Mrs. White', 
'Candlestick', 'Kitchen']
Unrefuted: ['Prof. Plum', 'Candlestick', 'Hall']
  [0] roll
  [1] ACCUSE (choose suspect + weapon + room)
Your action #: 0
P1 rolled [4, 6] = 10
╭─ Board (+ = door, X = cellar, S/M/W/G/K/P = tokens) ─╮
│     012345678901234567890123                         │
│  0           .bbbb.                                  │
│  1  kkkkkk....bbbb....cccccc                         │
│  2  kkkkkk..bbbbbbbb..cccccc                         │
│  3  KITCHk..bbbbbbbb..CONSEc                         │
│  4  kkkkkk..BALLROOb..cccccc                         │
│  5  kkkkkk.+bGKbbbbb+.cccccc                         │
│  6  kkkkkk..bbbbbbbb..+.....                         │
│  7   ...+...bbbbbbbb.......                          │
│  8   ........+....+...iiiiii                         │
│  9  dddddddd.........+iiiiii                         │
│ 10  dddddddd.XXXXXX...BILLIi                         │
│ 11  dddddddd.XXXXXX...iiiiii                         │
│ 12  DINING d+XXXXXX...iiiiii                         │
│ 13  dddddddd.XXXXXX.....+.+                          │
│ 14  dddddddd.XXXXXX..lllllll                         │
│ 15  dddddddd.XXXXXX..lllllll                         │
│ 16   .....+..XXXXXX.+LIBRARl                         │
│ 17  ...........++.M..lllllll                         │
│ 18   .....+..hhhhhh..lllllll                         │
│ 19  lllllll..hhhhhh.........                         │
│ 20  lllllll.+hhhhhh..+.....                          │
│ 21  LOUNGEl..hHALLh..sssssss                         │
│ 22  lllllll..hSWPhh..sSTUDYs                         │
│ 23  lllllll..hhhhhh..sssssss                         │
│ 24  lllllll. hhhhhh  sssssss                         │
╰──────────────────────────────────────────────────────╯
You are P1 (Miss Scarlet) at Hall  hand: Col. Mustard, Lead Pipe, Mr. Green, Revolver, Wrench
           Notebook           
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Card          ┃ Status     ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ Miss Scarlet  │ held by P4 │
│ Col. Mustard  │ mine       │
│ Mrs. White    │ held by P3 │
│ Mr. Green     │ mine       │
│ Mrs. Peacock  │ ?          │
│ Prof. Plum    │ ?          │
│ Candlestick   │ ?          │
│ Dagger        │ held by P2 │
│ Lead Pipe     │ mine       │
│ Revolver      │ mine       │
│ Rope          │ held by P2 │
│ Wrench        │ mine       │
│ Hall          │ ?          │
│ Lounge        │ held by P4 │
│ Dining Room   │ held by P2 │
│ Kitchen       │ ?          │
│ Ballroom      │ held by P2 │
│ Conservatory  │ held by P3 │
│ Billiard Room │ ?          │
│ Library       │ ?          │
│ Study         │ ?          │
└───────────────┴────────────┘
Constraints: P4 has one of ['Miss Scarlet', 'Dagger', 'Conservatory']; P4 has one of ['Mrs. Peacock', 
'Revolver', 'Lounge']; P4 has one of ['Mrs. Peacock', 'Revolver', 'Ballroom']; P3 has one of ['Prof. Plum', 
'Candlestick', 'Study']; P4 has one of ['Miss Scarlet', 'Wrench', 'Hall']; P2 has one of ['Mrs. White', 
'Candlestick', 'Kitchen']
Unrefuted: ['Prof. Plum', 'Candlestick', 'Hall']
  [0] move to=11,8
  [1] move to=16,3
  [2] move to=17,2
  [3] move to=18,1
  [4] move to=Dining Room
  [5] move to=Lounge
  [6] ACCUSE (choose suspect + weapon + room)
Your action #: 5
P1 moved Hall -> Lounge
╭─ Board (+ = door, X = cellar, S/M/W/G/K/P = tokens) ─╮
│     012345678901234567890123                         │
│  0           .bbbb.                                  │
│  1  kkkkkk....bbbb....cccccc                         │
│  2  kkkkkk..bbbbbbbb..cccccc                         │
│  3  KITCHk..bbbbbbbb..CONSEc                         │
│  4  kkkkkk..BALLROOb..cccccc                         │
│  5  kkkkkk.+bGKbbbbb+.cccccc                         │
│  6  kkkkkk..bbbbbbbb..+.....                         │
│  7   ...+...bbbbbbbb.......                          │
│  8   ........+....+...iiiiii                         │
│  9  dddddddd.........+iiiiii                         │
│ 10  dddddddd.XXXXXX...BILLIi                         │
│ 11  dddddddd.XXXXXX...iiiiii                         │
│ 12  DINING d+XXXXXX...iiiiii                         │
│ 13  dddddddd.XXXXXX.....+.+                          │
│ 14  dddddddd.XXXXXX..lllllll                         │
│ 15  dddddddd.XXXXXX..lllllll                         │
│ 16   .....+..XXXXXX.+LIBRARl                         │
│ 17  ...........++.M..lllllll                         │
│ 18   .....+..hhhhhh..lllllll                         │
│ 19  lllllll..hhhhhh.........                         │
│ 20  lllllll.+hhhhhh..+.....                          │
│ 21  LOUNGEl..hHALLh..sssssss                         │
│ 22  lSlllll..hWPhhh..sSTUDYs                         │
│ 23  lllllll..hhhhhh..sssssss                         │
│ 24  lllllll. hhhhhh  sssssss                         │
╰──────────────────────────────────────────────────────╯
You are P1 (Miss Scarlet) at Lounge  hand: Col. Mustard, Lead Pipe, Mr. Green, Revolver, Wrench
           Notebook           
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Card          ┃ Status     ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ Miss Scarlet  │ held by P4 │
│ Col. Mustard  │ mine       │
│ Mrs. White    │ held by P3 │
│ Mr. Green     │ mine       │
│ Mrs. Peacock  │ ?          │
│ Prof. Plum    │ ?          │
│ Candlestick   │ ?          │
│ Dagger        │ held by P2 │
│ Lead Pipe     │ mine       │
│ Revolver      │ mine       │
│ Rope          │ held by P2 │
│ Wrench        │ mine       │
│ Hall          │ ?          │
│ Lounge        │ held by P4 │
│ Dining Room   │ held by P2 │
│ Kitchen       │ ?          │
│ Ballroom      │ held by P2 │
│ Conservatory  │ held by P3 │
│ Billiard Room │ ?          │
│ Library       │ ?          │
│ Study         │ ?          │
└───────────────┴────────────┘
Constraints: P4 has one of ['Miss Scarlet', 'Dagger', 'Conservatory']; P4 has one of ['Mrs. Peacock', 
'Revolver', 'Lounge']; P4 has one of ['Mrs. Peacock', 'Revolver', 'Ballroom']; P3 has one of ['Prof. Plum', 
'Candlestick', 'Study']; P4 has one of ['Miss Scarlet', 'Wrench', 'Hall']; P2 has one of ['Mrs. White', 
'Candlestick', 'Kitchen']
Unrefuted: ['Prof. Plum', 'Candlestick', 'Hall']
  [0] end_turn
  [1] suggest (choose suspect + weapon)
  [2] ACCUSE (choose suspect + weapon + room)
Your action #: 1
  [0] Miss Scarlet
  [1] Col. Mustard
  [2] Mrs. White
  [3] Mr. Green
  [4] Mrs. Peacock
  [5] Prof. Plum
Suspect #: 5
  [0] Candlestick
  [1] Dagger
  [2] Lead Pipe
  [3] Revolver
  [4] Rope
  [5] Wrench
Weapon #: 4
P1 suggests: Prof. Plum with the Rope in the Lounge
  P2 can disprove...
  P2 showed the Rope to P1
╭─ Board (+ = door, X = cellar, S/M/W/G/K/P = tokens) ─╮
│     012345678901234567890123                         │
│  0           .bbbb.                                  │
│  1  kkkkkk....bbbb....cccccc                         │
│  2  kkkkkk..bbbbbbbb..cccccc                         │
│  3  KITCHk..bbbbbbbb..CONSEc                         │
│  4  kkkkkk..BALLROOb..cccccc                         │
│  5  kkkkkk.+bGKbbbbb+.cccccc                         │
│  6  kkkkkk..bbbbbbbb..+.....                         │
│  7   ...+...bbbbbbbb.......                          │
│  8   ........+....+...iiiiii                         │
│  9  dddddddd.........+iiiiii                         │
│ 10  dddddddd.XXXXXX...BILLIi                         │
│ 11  dddddddd.XXXXXX...iiiiii                         │
│ 12  DINING d+XXXXXX...iiiiii                         │
│ 13  dddddddd.XXXXXX.....+.+                          │
│ 14  dddddddd.XXXXXX..lllllll                         │
│ 15  dddddddd.XXXXXX..lllllll                         │
│ 16   .....+..XXXXXX.+LIBRARl                         │
│ 17  ...........++.M..lllllll                         │
│ 18   .....+..hhhhhh..lllllll                         │
│ 19  lllllll..hhhhhh.........                         │
│ 20  lllllll.+hhhhhh..+.....                          │
│ 21  LOUNGEl..hHALLh..sssssss                         │
│ 22  lSPllll..hWhhhh..sSTUDYs                         │
│ 23  lllllll..hhhhhh..sssssss                         │
│ 24  lllllll. hhhhhh  sssssss                         │
╰──────────────────────────────────────────────────────╯
You are P1 (Miss Scarlet) at Lounge  hand: Col. Mustard, Lead Pipe, Mr. Green, Revolver, Wrench
           Notebook           
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Card          ┃ Status     ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ Miss Scarlet  │ held by P4 │
│ Col. Mustard  │ mine       │
│ Mrs. White    │ held by P3 │
│ Mr. Green     │ mine       │
│ Mrs. Peacock  │ ?          │
│ Prof. Plum    │ ?          │
│ Candlestick   │ ?          │
│ Dagger        │ held by P2 │
│ Lead Pipe     │ mine       │
│ Revolver      │ mine       │
│ Rope          │ held by P2 │
│ Wrench        │ mine       │
│ Hall          │ ?          │
│ Lounge        │ held by P4 │
│ Dining Room   │ held by P2 │
│ Kitchen       │ ?          │
│ Ballroom      │ held by P2 │
│ Conservatory  │ held by P3 │
│ Billiard Room │ ?          │
│ Library       │ ?          │
│ Study         │ ?          │
└───────────────┴────────────┘
Constraints: P4 has one of ['Miss Scarlet', 'Dagger', 'Conservatory']; P4 has one of ['Mrs. Peacock', 
'Revolver', 'Lounge']; P4 has one of ['Mrs. Peacock', 'Revolver', 'Ballroom']; P3 has one of ['Prof. Plum', 
'Candlestick', 'Study']; P4 has one of ['Miss Scarlet', 'Wrench', 'Hall']; P2 has one of ['Mrs. White', 
'Candlestick', 'Kitchen']
Unrefuted: ['Prof. Plum', 'Candlestick', 'Hall']
  [0] end_turn
  [1] ACCUSE (choose suspect + weapon + room)
Your action #: 0
--- Turn 37: P2 ---
P2 rolled [3, 2] = 5
P2 moved 17,14 -> Library
P2 suggests: Prof. Plum with the Wrench in the Library
  P3 cannot disprove
  P4 can disprove...
  P4 showed a card to P2
--- Turn 38: P3 ---
P3 rolled [3, 3] = 6
P3 moved Hall -> Lounge
P3 suggests: Col. Mustard with the Revolver in the Lounge
  P4 can disprove...
  P4 showed a card to P3
--- Turn 39: P4 ---
P4 rolled [2, 6] = 8
P4 moved Ballroom -> Dining Room
P4 suggests: Mrs. White with the Candlestick in the Dining Room
  P1 cannot disprove
  P2 can disprove...
  P2 showed a card to P4
--- Turn 40: P1 ---
╭─ Board (+ = door, X = cellar, S/M/W/G/K/P = tokens) ─╮
│     012345678901234567890123                         │
│  0           .bbbb.                                  │
│  1  kkkkkk....bbbb....cccccc                         │
│  2  kkkkkk..bbbbbbbb..cccccc                         │
│  3  KITCHk..bbbbbbbb..CONSEc                         │
│  4  kkkkkk..BALLROOb..cccccc                         │
│  5  kkkkkk.+bKbbbbbb+.cccccc                         │
│  6  kkkkkk..bbbbbbbb..+.....                         │
│  7   ...+...bbbbbbbb.......                          │
│  8   ........+....+...iiiiii                         │
│  9  dddddddd.........+iiiiii                         │
│ 10  dddddddd.XXXXXX...BILLIi                         │
│ 11  dddddddd.XXXXXX...iiiiii                         │
│ 12  DINING d+XXXXXX...iiiiii                         │
│ 13  dWGddddd.XXXXXX.....+.+                          │
│ 14  dddddddd.XXXXXX..lllllll                         │
│ 15  dddddddd.XXXXXX..lllllll                         │
│ 16   .....+..XXXXXX.+LIBRARl                         │
│ 17  ...........++....lPlllll                         │
│ 18   .....+..hhhhhh..lllllll                         │
│ 19  lllllll..hhhhhh.........                         │
│ 20  lllllll.+hhhhhh..+.....                          │
│ 21  LOUNGEl..hHALLh..sssssss                         │
│ 22  lSMllll..hhhhhh..sSTUDYs                         │
│ 23  lllllll..hhhhhh..sssssss                         │
│ 24  lllllll. hhhhhh  sssssss                         │
╰──────────────────────────────────────────────────────╯
You are P1 (Miss Scarlet) at Lounge  hand: Col. Mustard, Lead Pipe, Mr. Green, Revolver, Wrench
           Notebook           
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Card          ┃ Status     ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ Miss Scarlet  │ held by P4 │
│ Col. Mustard  │ mine       │
│ Mrs. White    │ held by P3 │
│ Mr. Green     │ mine       │
│ Mrs. Peacock  │ ?          │
│ Prof. Plum    │ ?          │
│ Candlestick   │ ?          │
│ Dagger        │ held by P2 │
│ Lead Pipe     │ mine       │
│ Revolver      │ mine       │
│ Rope          │ held by P2 │
│ Wrench        │ mine       │
│ Hall          │ ?          │
│ Lounge        │ held by P4 │
│ Dining Room   │ held by P2 │
│ Kitchen       │ ?          │
│ Ballroom      │ held by P2 │
│ Conservatory  │ held by P3 │
│ Billiard Room │ ?          │
│ Library       │ ?          │
│ Study         │ ?          │
└───────────────┴────────────┘
Constraints: P3 has one of ['Prof. Plum', 'Candlestick', 'Study']; P4 has one of ['Miss Scarlet', 'Wrench', 
'Hall']; P2 has one of ['Mrs. White', 'Candlestick', 'Kitchen']; P4 has one of ['Prof. Plum', 'Wrench', 
'Library']; P4 has one of ['Col. Mustard', 'Revolver', 'Lounge']; P2 has one of ['Mrs. White', 'Candlestick', 
'Dining Room']
Unrefuted: ['Prof. Plum', 'Candlestick', 'Hall']
  [0] roll
  [1] passage
  [2] ACCUSE (choose suspect + weapon + room)
Your action #: 0
P1 rolled [3, 6] = 9
╭─ Board (+ = door, X = cellar, S/M/W/G/K/P = tokens) ─╮
│     012345678901234567890123                         │
│  0           .bbbb.                                  │
│  1  kkkkkk....bbbb....cccccc                         │
│  2  kkkkkk..bbbbbbbb..cccccc                         │
│  3  KITCHk..bbbbbbbb..CONSEc                         │
│  4  kkkkkk..BALLROOb..cccccc                         │
│  5  kkkkkk.+bKbbbbbb+.cccccc                         │
│  6  kkkkkk..bbbbbbbb..+.....                         │
│  7   ...+...bbbbbbbb.......                          │
│  8   ........+....+...iiiiii                         │
│  9  dddddddd.........+iiiiii                         │
│ 10  dddddddd.XXXXXX...BILLIi                         │
│ 11  dddddddd.XXXXXX...iiiiii                         │
│ 12  DINING d+XXXXXX...iiiiii                         │
│ 13  dWGddddd.XXXXXX.....+.+                          │
│ 14  dddddddd.XXXXXX..lllllll                         │
│ 15  dddddddd.XXXXXX..lllllll                         │
│ 16   .....+..XXXXXX.+LIBRARl                         │
│ 17  ...........++....lPlllll                         │
│ 18   .....+..hhhhhh..lllllll                         │
│ 19  lllllll..hhhhhh.........                         │
│ 20  lllllll.+hhhhhh..+.....                          │
│ 21  LOUNGEl..hHALLh..sssssss                         │
│ 22  lSMllll..hhhhhh..sSTUDYs                         │
│ 23  lllllll..hhhhhh..sssssss                         │
│ 24  lllllll. hhhhhh  sssssss                         │
╰──────────────────────────────────────────────────────╯
You are P1 (Miss Scarlet) at Lounge  hand: Col. Mustard, Lead Pipe, Mr. Green, Revolver, Wrench
           Notebook           
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Card          ┃ Status     ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ Miss Scarlet  │ held by P4 │
│ Col. Mustard  │ mine       │
│ Mrs. White    │ held by P3 │
│ Mr. Green     │ mine       │
│ Mrs. Peacock  │ ?          │
│ Prof. Plum    │ ?          │
│ Candlestick   │ ?          │
│ Dagger        │ held by P2 │
│ Lead Pipe     │ mine       │
│ Revolver      │ mine       │
│ Rope          │ held by P2 │
│ Wrench        │ mine       │
│ Hall          │ ?          │
│ Lounge        │ held by P4 │
│ Dining Room   │ held by P2 │
│ Kitchen       │ ?          │
│ Ballroom      │ held by P2 │
│ Conservatory  │ held by P3 │
│ Billiard Room │ ?          │
│ Library       │ ?          │
│ Study         │ ?          │
└───────────────┴────────────┘
Constraints: P3 has one of ['Prof. Plum', 'Candlestick', 'Study']; P4 has one of ['Miss Scarlet', 'Wrench', 
'Hall']; P2 has one of ['Mrs. White', 'Candlestick', 'Kitchen']; P4 has one of ['Prof. Plum', 'Wrench', 
'Library']; P4 has one of ['Col. Mustard', 'Revolver', 'Lounge']; P2 has one of ['Mrs. White', 'Candlestick', 
'Dining Room']
Unrefuted: ['Prof. Plum', 'Candlestick', 'Hall']
  [0] move to=12,8
  [1] move to=17,13
  [2] move to=Dining Room
  [3] move to=Hall
  [4] ACCUSE (choose suspect + weapon + room)
Your action #: 3
P1 moved Lounge -> Hall
╭─ Board (+ = door, X = cellar, S/M/W/G/K/P = tokens) ─╮
│     012345678901234567890123                         │
│  0           .bbbb.                                  │
│  1  kkkkkk....bbbb....cccccc                         │
│  2  kkkkkk..bbbbbbbb..cccccc                         │
│  3  KITCHk..bbbbbbbb..CONSEc                         │
│  4  kkkkkk..BALLROOb..cccccc                         │
│  5  kkkkkk.+bKbbbbbb+.cccccc                         │
│  6  kkkkkk..bbbbbbbb..+.....                         │
│  7   ...+...bbbbbbbb.......                          │
│  8   ........+....+...iiiiii                         │
│  9  dddddddd.........+iiiiii                         │
│ 10  dddddddd.XXXXXX...BILLIi                         │
│ 11  dddddddd.XXXXXX...iiiiii                         │
│ 12  DINING d+XXXXXX...iiiiii                         │
│ 13  dWGddddd.XXXXXX.....+.+                          │
│ 14  dddddddd.XXXXXX..lllllll                         │
│ 15  dddddddd.XXXXXX..lllllll                         │
│ 16   .....+..XXXXXX.+LIBRARl                         │
│ 17  ...........++....lPlllll                         │
│ 18   .....+..hhhhhh..lllllll                         │
│ 19  lllllll..hhhhhh.........                         │
│ 20  lllllll.+hhhhhh..+.....                          │
│ 21  LOUNGEl..hHALLh..sssssss                         │
│ 22  lMlllll..hShhhh..sSTUDYs                         │
│ 23  lllllll..hhhhhh..sssssss                         │
│ 24  lllllll. hhhhhh  sssssss                         │
╰──────────────────────────────────────────────────────╯
You are P1 (Miss Scarlet) at Hall  hand: Col. Mustard, Lead Pipe, Mr. Green, Revolver, Wrench
           Notebook           
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Card          ┃ Status     ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ Miss Scarlet  │ held by P4 │
│ Col. Mustard  │ mine       │
│ Mrs. White    │ held by P3 │
│ Mr. Green     │ mine       │
│ Mrs. Peacock  │ ?          │
│ Prof. Plum    │ ?          │
│ Candlestick   │ ?          │
│ Dagger        │ held by P2 │
│ Lead Pipe     │ mine       │
│ Revolver      │ mine       │
│ Rope          │ held by P2 │
│ Wrench        │ mine       │
│ Hall          │ ?          │
│ Lounge        │ held by P4 │
│ Dining Room   │ held by P2 │
│ Kitchen       │ ?          │
│ Ballroom      │ held by P2 │
│ Conservatory  │ held by P3 │
│ Billiard Room │ ?          │
│ Library       │ ?          │
│ Study         │ ?          │
└───────────────┴────────────┘
Constraints: P3 has one of ['Prof. Plum', 'Candlestick', 'Study']; P4 has one of ['Miss Scarlet', 'Wrench', 
'Hall']; P2 has one of ['Mrs. White', 'Candlestick', 'Kitchen']; P4 has one of ['Prof. Plum', 'Wrench', 
'Library']; P4 has one of ['Col. Mustard', 'Revolver', 'Lounge']; P2 has one of ['Mrs. White', 'Candlestick', 
'Dining Room']
Unrefuted: ['Prof. Plum', 'Candlestick', 'Hall']
  [0] end_turn
  [1] suggest (choose suspect + weapon)
  [2] ACCUSE (choose suspect + weapon + room)
Your action #: 1
  [0] Miss Scarlet
  [1] Col. Mustard
  [2] Mrs. White
  [3] Mr. Green
  [4] Mrs. Peacock
  [5] Prof. Plum
Suspect #: 4
  [0] Candlestick
  [1] Dagger
  [2] Lead Pipe
  [3] Revolver
  [4] Rope
  [5] Wrench
Weapon #: 4
P1 suggests: Mrs. Peacock with the Rope in the Hall
  P2 can disprove...
  P2 showed the Rope to P1
╭─ Board (+ = door, X = cellar, S/M/W/G/K/P = tokens) ─╮
│     012345678901234567890123                         │
│  0           .bbbb.                                  │
│  1  kkkkkk....bbbb....cccccc                         │
│  2  kkkkkk..bbbbbbbb..cccccc                         │
│  3  KITCHk..bbbbbbbb..CONSEc                         │
│  4  kkkkkk..BALLROOb..cccccc                         │
│  5  kkkkkk.+bbbbbbbb+.cccccc                         │
│  6  kkkkkk..bbbbbbbb..+.....                         │
│  7   ...+...bbbbbbbb.......                          │
│  8   ........+....+...iiiiii                         │
│  9  dddddddd.........+iiiiii                         │
│ 10  dddddddd.XXXXXX...BILLIi                         │
│ 11  dddddddd.XXXXXX...iiiiii                         │
│ 12  DINING d+XXXXXX...iiiiii                         │
│ 13  dWGddddd.XXXXXX.....+.+                          │
│ 14  dddddddd.XXXXXX..lllllll                         │
│ 15  dddddddd.XXXXXX..lllllll                         │
│ 16   .....+..XXXXXX.+LIBRARl                         │
│ 17  ...........++....lPlllll                         │
│ 18   .....+..hhhhhh..lllllll                         │
│ 19  lllllll..hhhhhh.........                         │
│ 20  lllllll.+hhhhhh..+.....                          │
│ 21  LOUNGEl..hHALLh..sssssss                         │
│ 22  lMlllll..hSKhhh..sSTUDYs                         │
│ 23  lllllll..hhhhhh..sssssss                         │
│ 24  lllllll. hhhhhh  sssssss                         │
╰──────────────────────────────────────────────────────╯
You are P1 (Miss Scarlet) at Hall  hand: Col. Mustard, Lead Pipe, Mr. Green, Revolver, Wrench
           Notebook           
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Card          ┃ Status     ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ Miss Scarlet  │ held by P4 │
│ Col. Mustard  │ mine       │
│ Mrs. White    │ held by P3 │
│ Mr. Green     │ mine       │
│ Mrs. Peacock  │ ?          │
│ Prof. Plum    │ ?          │
│ Candlestick   │ ?          │
│ Dagger        │ held by P2 │
│ Lead Pipe     │ mine       │
│ Revolver      │ mine       │
│ Rope          │ held by P2 │
│ Wrench        │ mine       │
│ Hall          │ ?          │
│ Lounge        │ held by P4 │
│ Dining Room   │ held by P2 │
│ Kitchen       │ ?          │
│ Ballroom      │ held by P2 │
│ Conservatory  │ held by P3 │
│ Billiard Room │ ?          │
│ Library       │ ?          │
│ Study         │ ?          │
└───────────────┴────────────┘
Constraints: P3 has one of ['Prof. Plum', 'Candlestick', 'Study']; P4 has one of ['Miss Scarlet', 'Wrench', 
'Hall']; P2 has one of ['Mrs. White', 'Candlestick', 'Kitchen']; P4 has one of ['Prof. Plum', 'Wrench', 
'Library']; P4 has one of ['Col. Mustard', 'Revolver', 'Lounge']; P2 has one of ['Mrs. White', 'Candlestick', 
'Dining Room']
Unrefuted: ['Prof. Plum', 'Candlestick', 'Hall']
  [0] end_turn
  [1] ACCUSE (choose suspect + weapon + room)
Your action #: 0
--- Turn 41: P2 ---
P2 suggests: Mr. Green with the Lead Pipe in the Lounge
  P3 cannot disprove
  P4 can disprove...
  P4 showed a card to P2
--- Turn 42: P3 ---
P3 suggests: Col. Mustard with the Rope in the Dining Room
  P4 cannot disprove
  P1 can disprove...
P3 suggested Col. Mustard / Rope / Dining Room. You must show a card.
Showing Col. Mustard
  P1 showed the Col. Mustard to P3
P3 ACCUSES Prof. Plum / Candlestick / Hall -> CORRECT
GAME OVER. Winner: P3. Solution: ['Prof. Plum', 'Candlestick', 'Hall']
```

## Replay privacy check

The unredacted replay (`replays/game_42.jsonl`) contains every shown card; the redacted view for P3 (`replays/game_42_redacted_P3.json`) shows `disproved` events without a `card` field unless P3 was involved:

```json
// unredacted
{'seq': 10, 'kind': 'event', 'type': 'disproved', 'turn': 0, 'player': 'P2', 'suggester': 'P1', 'disprover': 'P2', 'card': 'Rope'}
{'seq': 53, 'kind': 'event', 'type': 'disproved', 'turn': 2, 'player': 'P1', 'suggester': 'P3', 'disprover': 'P1', 'card': 'Mr. Green'}
{'seq': 64, 'kind': 'event', 'type': 'disproved', 'turn': 3, 'player': 'P1', 'suggester': 'P4', 'disprover': 'P1', 'card': 'Revolver'}
{'seq': 75, 'kind': 'event', 'type': 'disproved', 'turn': 4, 'player': 'P2', 'suggester': 'P1', 'disprover': 'P2', 'card': 'Dagger'}
// redacted for P3
{'seq': 10, 'kind': 'event', 'type': 'disproved', 'turn': 0, 'player': 'P2', 'suggester': 'P1', 'disprover': 'P2'}
{'seq': 53, 'kind': 'event', 'type': 'disproved', 'turn': 2, 'player': 'P1', 'suggester': 'P3', 'disprover': 'P1', 'card': 'Mr. Green'}
{'seq': 64, 'kind': 'event', 'type': 'disproved', 'turn': 3, 'player': 'P1', 'suggester': 'P4', 'disprover': 'P1'}
{'seq': 75, 'kind': 'event', 'type': 'disproved', 'turn': 4, 'player': 'P2', 'suggester': 'P1', 'disprover': 'P2'}
```