# Auto Play Strategy: tower

## Objective
- Keep fighting and progress as far as possible through the tower.

## Preferred Buttons
- Adventure
- Enter Adventure
- 冒险
- 进入冒险
- 战斗
- 开战
- 挑战
- 爬塔
- Fight
- Battle
- Sword
- Normal Sword
- 普通小剑
- Chest
- Treasure
- 宝箱
- Take Treasure
- 拿走前辈的宝物
- Backpack Room
- Professional Backpack
- 职业背包
- Scroll Room
- Paper Room
- 卷轴房间
- Giant Fist
- 巨人之拳
- Offensive Treasure
- Battle Focus
- 战斗专注
- Combat Card
- Attack
- Challenge
- Start
- Play
- Continue
- Resume Adventure
- 恢复冒险
- Next Room
- Down Arrow
- 下一房间
- 前进
- Move Right
- Right Path
- 右侧道路
- Next
- OK
- Claim
- Collect
- Pick Up
- Pick Up Weapon
- 捡起
- 捡起木剑
- Merge Weapon
- Upgrade Weapon
- 融合武器
- Merge Card
- Upgrade Card
- 融合卡牌
- Resume
- Accept
- Dismiss Reward
- Close Reward
- 点击空白处关闭
- Retry
- Again

## Avoid Buttons
- Exit
- Cancel
- Back
- Store
- Shop
- Buy
- Purchase
- Ad
- Ads
- Settings
- 设置
- Task
- 任务
- Fusion
- 融合
- Abandon Adventure
- 放弃冒险

## Ineffective Buttons
- [6
- ↑!
- Scroll Room
- Chest
- Obtained Loot

## Decision Rules
- Prefer adventure, fight, battle, attack, challenge, start, continue, and retry actions.
- Prefer resume adventure when a previous tower fight can be continued.
- Prefer next-room or down-arrow controls when no enemy is visible in the current room.
- Prefer sword/combat room choices over treasure, backpack, or utility rooms.
- If no combat room is available, prefer treasure/chest rooms over backpack or utility rooms.
- If only a backpack or utility room remains, choose it to keep the dungeon moving.
- Choose concrete room icons over small connector arrows; connector arrows may only animate the map.
- If map-room clicks do not open an event, tap the open path in the top playfield to move the hero.
- In treasure selection, prefer offensive fight-scaling options such as Giant Fist.
- In card learning, prefer combat focus or fight-scaling cards over cards that spend health.
- On treasure selection screens, select the desired treasure card before pressing Confirm.
- Prefer actions that continue combat over reward collection when both are available.
- Pick up weapons or combat gear when offered because it improves fighting.
- Merge or upgrade weapons when a reward upgrade panel is already open.
- Merge or upgrade combat cards when a reward upgrade panel is already open.
- Close reward popups after collecting gear so the run can continue.
- Avoid abandon adventure, shop, purchase, ad, settings, task, fusion, back, cancel, and exit actions.
- If multiple fight-like actions are plausible, try the highest-scored option first.
- If an action does not change the screen after retries, remember it as ineffective and try a different fight-like option on the next turn.

## Learned Choices
- The user said the tower strategy is to keep fighting.
- Choose **进入冒险** / **Enter Adventure** over the bottom Adventure tab when a selected stage is visible because it starts the selected tower fight.
- Choose **恢复冒险** / **Resume Adventure** instead of **放弃冒险** / **Abandon Adventure** because resuming keeps fighting.
- Choose the bottom-center down arrow when the dungeon room has no enemy because it advances toward the next fight.
- Choose **普通小剑** / **Normal Sword** when room choices appear because it is the fight-like route.
- On the branch map, the small up-arrow can highlight/shift focus without advancing; choose a concrete room icon instead.
- Choose treasure/chest only when no fight-like room is available.
- Choose backpack/utility rooms only when fight-like and treasure rooms are not available.
- Choose scroll/paper rooms when they are the only remaining concrete room icon.
- If the map appears stuck after clearing room rewards, use the top playfield path direction rather than the map.
- If a treasure room has already been selected, take the treasure rather than hesitating.
- Choose **巨人之拳** / **Giant Fist** when offered as a treasure because it appears more offensive than defensive/utility options.
- Do not press generic **Confirm** before selecting the desired treasure; it accepts the current default selection.
- Choose **战斗专注** / **Battle Focus** over self-damage cards when learning cards because it sounds like a safer combat buff.
- Choose **捡起** / **Pick Up** for weapons and combat gear because it supports the keep-fighting strategy.
- Choose **融合** on the weapon reward upgrade panel because it improves combat gear; do not treat the side-panel fusion shortcut as a fight action.
- Choose **融合** on combat-card reward upgrade panels because it improves fighting cards.
- Tap blank space to close reward popups after the reward is obtained.

## Strategy Improvements Needed
- Treat **[6** as ineffective unless another cue confirms it advances play; after 3 repeated attempts, prefer a different progression action or ask for vision/user input.
- Treat **↑!** as ineffective unless another cue confirms it advances play; after 3 repeated attempts, prefer a different progression action or ask for vision/user input.
- Treat **Scroll Room** as ineffective unless another cue confirms it advances play; after 3 repeated attempts, prefer a different progression action or ask for vision/user input.
- Treat **Chest** as ineffective unless another cue confirms it advances play; after 3 repeated attempts, prefer a different progression action or ask for vision/user input.
- Treat **Obtained Loot** as ineffective unless another cue confirms it advances play; after 3 repeated attempts, prefer a different progression action or ask for vision/user input.

## Notes
- This file stores durable strategy only. Do not record transient screen state here.
