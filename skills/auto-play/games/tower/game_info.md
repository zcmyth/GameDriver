# Game Info: tower

This file stores durable descriptions captured from item inspections, explicit LLM game info, and durable LLM object captures. Ranking uses the same preference score as auto-play item selection when enough text is known. Entries are grouped by type and sorted by score descending within each type.

## Ranking

### item

| Rank | Name | Score | Seen | Sources | Cues | Description | Last Seen |
| ---: | --- | ---: | ---: | --- | --- | --- | --- |
| 1 | 迅捷攻击 | 4.00 | 4 | item inspection | stat increase | description not captured | 20260630T220007-0700-tower |
| 2 | Abandon | 0.00 | 3 | item inspection | observed detail | description not captured | 20260524T120314-0700-tower |
| 3 | EAZ | 0.00 | 2 | item inspection | observed detail | Abandon; EAZ | 20260524T115919-0700-tower |
| 4 | 战术准备 | 0.00 | 1 | item inspection | observed detail | Abandon | 20260524T111726-0700-tower |
| 5 | 法术绒帽 | 0.00 | 2 | llm game_info | observed detail | 回合开始时：向抽牌堆加入1张能量飞弹* | 20260630T213721-0700-tower |
| 6 | 舍命一击 | -8.00 | 2 | item inspection | self-sacrifice cue | Abandon | 20260524T120314-0700-tower |

### skill

| Rank | Name | Score | Seen | Sources | Cues | Description | Last Seen |
| ---: | --- | ---: | ---: | --- | --- | --- | --- |
| 1 | 闪耀挥击 | 2.00 | 5 | item inspection, llm game_info | cost or loss, increase cue, observed detail, stat increase | 消耗: 物理伤害: 2 每装备1张宝石牌，物理伤害+1 | 20260524T111726-0700-tower |


## Captured Descriptions

### item

#### 1. 迅捷攻击
- Type: item
- Rank score: 4.00
- Seen count: 4
- Sources: item inspection
- First seen: 20260630T213632-0700-tower
- Last seen: 20260630T220007-0700-tower
- Cues: stat increase
- Description: description not captured
- Last screenshot: /Users/chunzhang/game_driver/skills/auto-play/games/tower/turns/20260630T220007-0700-tower/item_inspections/03-迅捷攻击.png

#### 2. Abandon
- Type: item
- Rank score: 0.00
- Seen count: 3
- Sources: item inspection
- First seen: 20260524T112030-0700-tower
- Last seen: 20260524T120314-0700-tower
- Cues: observed detail
- Description: description not captured
- Last screenshot: /Users/chunzhang/game_driver/skills/auto-play/games/tower/turns/20260524T120314-0700-tower/item_inspections/02-abandon.png

#### 3. EAZ
- Type: item
- Rank score: 0.00
- Seen count: 2
- Sources: item inspection
- First seen: 20260524T112030-0700-tower
- Last seen: 20260524T115919-0700-tower
- Cues: observed detail
- Description: Abandon; EAZ
- Last screenshot: /Users/chunzhang/game_driver/skills/auto-play/games/tower/turns/20260524T115919-0700-tower/item_inspections/01-eaz.png

#### 4. 战术准备
- Type: item
- Rank score: 0.00
- Seen count: 1
- Sources: item inspection
- First seen: 20260524T111726-0700-tower
- Last seen: 20260524T111726-0700-tower
- Cues: observed detail
- Description: Abandon
- Last screenshot: /Users/chunzhang/game_driver/skills/auto-play/games/tower/turns/20260524T111726-0700-tower/item_inspections/03-战术准备.png

#### 5. 法术绒帽
- Type: item
- Rank score: 0.00
- Seen count: 2
- Sources: llm game_info
- First seen: 20260630T213652-0700-tower
- Last seen: 20260630T213721-0700-tower
- Cues: observed detail
- Description: 回合开始时：向抽牌堆加入1张能量飞弹*
- Last screenshot: /Users/chunzhang/game_driver/skills/auto-play/games/tower/turns/20260630T213721-0700-tower/screenshot.png

#### 6. 舍命一击
- Type: item
- Rank score: -8.00
- Seen count: 2
- Sources: item inspection
- First seen: 20260524T111726-0700-tower
- Last seen: 20260524T120314-0700-tower
- Cues: self-sacrifice cue
- Description: Abandon
- Last screenshot: /Users/chunzhang/game_driver/skills/auto-play/games/tower/turns/20260524T120314-0700-tower/item_inspections/01-舍命一击.png

### skill

#### 1. 闪耀挥击
- Type: skill
- Rank score: 2.00
- Seen count: 5
- Sources: item inspection, llm game_info
- First seen: 20260524T111726-0700-tower
- Last seen: 20260524T111726-0700-tower
- Cues: cost or loss, increase cue, observed detail, stat increase
- Description: 消耗: 物理伤害: 2 每装备1张宝石牌，物理伤害+1
- Last screenshot: /Users/chunzhang/game_driver/skills/auto-play/games/tower/turns/20260524T111726-0700-tower/screenshot.png
