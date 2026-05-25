# Auto Play Strategy: tower

## Objective
- Keep fighting and progress as far as possible through the tower.

## Preferred Buttons
- Adventure
- Enter Adventure
- Start Adventure
- 冒险
- 进入冒险
- 开始冒险
- 战斗
- 开战
- 挑战
- 幼虫
- 岩壳龙
- 大龙
- 爬塔
- Fight
- Battle
- Sword
- Normal Sword
- 普通小剑
- 普通木剑
- Normal Attack
- 普通攻击
- 举盾
- 盲刃
- 发现弱点
- 迅捷攻击
- 迅捷
- 转身准备
- 弱点打击
- 专注宝石
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
- 强化法阵
- Giant Fist
- 巨人之拳
- Offensive Treasure
- Battle Focus
- 战斗专注
- 无限攻击
- 归一
- 启动防守
- Combat Card
- Attack
- Challenge
- Start
- Play
- Continue
- Resume Adventure
- 恢复冒险
- Recruit
- Recruit Adventurer
- 招募
- 招募冒险者
- Hire
- Hire Adventurer
- 雇佣
- Next
- OK
- Claim
- Collect
- Pick Up
- Pick Up Weapon
- 捡起
- 捡起木剑
- 强化
- Merge Weapon
- Upgrade Weapon
- 融合武器
- Merge Card
- Upgrade Card
- 融合卡牌
- Resume
- Accept
- Return to Inn
- 返回旅馆
- Dismiss Reward
- Close Reward
- 关闭侧边栏
- 关闭分享面板
- 点击空白处关闭
- Retry
- Again
- 拨弄他的吉他
- 拨弄他的吉他。

## Avoid Buttons
- Abandon Adventure
- 放弃冒险
- 他睡得好香，让他继续睡。
- 他睡得好香 让他继续睡
- 继续睡
- Reject
- Refuse
- 拒绝
- 稍后再说
- 遗忘法阵
- Forget Card
- Tap

## Ineffective Buttons
None yet.

## Fallback Buttons
- Next Room
- Down Arrow
- Up Arrow
- Left Arrow
- Right Arrow
- Move Left
- Move Right
- Left Path
- Right Path
- 下一房间
- 前进
- 上方道路
- 下方道路
- 左侧道路
- 右侧道路
- ↑
- ↓
- ←
- →

## Decision Rules
- Prefer adventure, fight, battle, attack, challenge, start, continue, and retry actions.
- On the stage loadout screen, click **开始冒险** / **Start Adventure** to begin
  the selected run.
- Prefer resume adventure when a previous tower fight can be continued.
- On a defeat screen (`游戏失败`), click **返回旅馆** / **Return to Inn** so the
  next run can start from the inn instead of tapping stat labels.
- If the game says there is no usable adventurer (`当前无可用冒险者，请前往旅馆招募`),
  return to the inn and click **招募** / **Recruit** before trying Adventure again.
- On the recruit detail screen, click **雇佣** / **Hire** to add the adventurer;
  do not click **拒绝** or the back control unless hire is unavailable.
- After hiring succeeds and the new adventurer formally joins, click
  **进入冒险** and avoid **稍后再说**.
- Prefer strength-building actions before navigation arrows: weapons, treasure, chest rooms, backpack/utility rooms, scroll/card rooms, combat cards, merge/upgrade actions, and reward pickups can improve the character.
- Use arrow/path controls only when there is no visible fight, reward, room choice, equipment, treasure, card, chest, backpack, merge, pickup, confirm-after-selection, or other strength-building action available.
- When choosing between items/cards/treasures, tap each option first to reveal and OCR its description, remember the description, then select the best option and confirm it.
- In item choices, always prefer permanent stat changes first, then coin gain, then stat increases that trigger per battle or every battle.
- Prefer sword/combat room choices over treasure, backpack, or utility rooms.
- If no combat room is available, prefer treasure/chest rooms over backpack or utility rooms because they can improve character strength.
- If only a backpack or utility room remains, choose it to keep the dungeon moving.
- Choose concrete room icons over small connector arrows; connector arrows may only animate the map.
- When only room-movement arrows are available and two arrows are visible, choose the brighter/highlighted arrow. A dim arrow usually means an unavailable or non-progressing route.
- If movement arrows alternate between two views (for example left, right,
  left, right), treat that as a DFS backtracking loop and avoid the two
  reversing arrows on the next turn; choose another visible route such as the
  up/down arrow or a new concrete room icon.
- For room movement, click the tight center of the highlighted arrow icon
  itself. Do not use broad room-panel crops such as the old `下一房间` template
  because they can land outside the arrow and repeat without moving.
- Add labels to Avoid Buttons only when we have high confidence that they are
  run-ending, clearly harmful, or the user explicitly rejected them. Put
  uncertain choices, low-confidence OCR labels, and one-off no-change actions
  in the turn worklog/metadata until there is enough evidence to update a real
  strategy rule.
- Add labels to Ineffective Buttons only when we have high-confidence repeated
  evidence that a concrete action never progresses in this game. Do not add OCR
  noise, stat text, useful combat/card actions, start/confirm actions, or
  context-dependent buttons here after a single failed click.
- If map-room clicks do not open an event, tap the open path in the top playfield to move the hero.
- On the in-run room map, click the visible enemy/current-room icon such as
  **幼虫** to start the encounter; do not treat its `Lv.1` label as the action.
- In treasure selection, prefer offensive fight-scaling options such as Giant Fist.
- In card learning, prefer combat focus or fight-scaling cards over cards that spend health.
- On card-learning screens (`选一张卡牌学习`), never click **Abandon**; select
  the best visible card first, then click **确定** / **Confirm**.
- On treasure selection screens, select the desired treasure card before pressing Confirm.
- Prefer actions that continue combat over reward collection when both are available.
- During combat, play visible attack, damage, shield, focus, or treasure-card
  buttons before ending the turn.
- If **End** and a combat card such as **普通攻击**, **普通木剑**, or **举盾**
  are both visible, play the card before ending the turn.
- If OCR only sees **End** but the hand contains visible combat cards, learn or
  use card templates and play the cards before ending the turn.
- If combat-card templates appear on the room map while no **End** button is
  visible and a bright route arrow is visible, treat those card hits as stale
  template matches and click the bright route arrow instead.
- Combat cards are played by double-tapping the same card: the first tap selects
  it and the second tap confirms/uses it. Do not target the enemy portrait or
  the prompt arrow for normal combat card play.
- Click **End** only when there are no playable combat cards or other useful
  actions left.
- Pick up weapons or combat gear when offered because it improves fighting.
- Merge or upgrade weapons when a reward upgrade panel is already open.
- Merge or upgrade combat cards when a reward upgrade panel is already open.
- On **Enhance Card** selected-card panels, click **强化** to apply the upgrade;
  do not click **返回** unless there is no visible enhance/merge/confirm action.
- Close reward popups after collecting gear so the run can continue.
- On a revive/ad prompt, choose **Cancel** instead of watching an ad, then use
  the normal defeat recovery path.
- If multiple fight-like actions are plausible, try the highest-scored option first.
- If an action does not change the screen after retries, try a different
  fight-like option on the next turn; only update Ineffective Buttons after
  repeated high-confidence evidence.
- Do not treat standalone stat delta text such as **±2**, **+4**, or **+5** as an action; those are descriptive values, not buttons.
- When the last few turn screenshots remain nearly identical, temporarily deprioritize repeated actions and try a different visible target, tutorial-highlighted control, close/detail/back control, or vision-identified clickable before retrying.
- When a room arrow fails to change the screen after retries, pick the brighter route or a concrete room icon before retrying that arrow.

## Learned Choices
- The user said the tower strategy is to keep fighting.
- Choose **进入冒险** / **Enter Adventure** over the bottom Adventure tab when a selected stage is visible because it starts the selected tower fight.
- Choose **开始冒险** / **Start Adventure** on the stage loadout screen because it
  launches the selected fight.
- Choose **幼虫** on the first in-run map because it is the visible enemy room
  that starts the encounter; ignore the adjacent `Lv.1` text as a label.
- Choose **岩壳龙** on the in-run map when visible because it is another enemy
  room that starts an encounter; ignore its `Lv.1` label as a standalone action.
- Choose **大龙** on the in-run map when visible because it is a higher-level
  enemy room that starts an encounter; ignore its `Lv.2` label as a standalone action.
- Choose **恢复冒险** / **Resume Adventure** instead of **放弃冒险** / **Abandon Adventure** because resuming keeps fighting.
- Choose **返回旅馆** / **Return to Inn** after defeat because it recovers to a
  playable state where the next tower attempt can begin.
- If the inn/adventure flow loops through `当前无可用冒险者，请前往旅馆招募`,
  choose **招募** on the inn panel before tapping **冒险** again.
- After recruiting reveals an adventurer detail sheet, choose **雇佣** because
  hiring restores a playable adventurer and should unblock the next run.
- When the `正式加入！` screen appears, click **进入冒险** because the new
  adventurer is ready for the tower run.
- Choose arrows only as fallback navigation when no better strength-building or event action is visible; improving the character is more valuable than blindly advancing.
- Choose **普通小剑** / **Normal Sword** when room choices appear because it is the fight-like route.
- On the branch map, the small up-arrow can highlight/shift focus without advancing; choose a concrete room icon instead.
- Choose treasure/chest rooms when no fight-like room is available because they can increase strength.
- Choose backpack/utility rooms when fight-like and treasure rooms are not available because utility can still improve the character.
- Choose scroll/paper rooms before arrows because cards/scrolls can improve future fights.
- If the map appears stuck after clearing room rewards, use the top playfield path direction rather than the map.
- If the map shows the already-cleared/current room icon plus a bright exit
  arrow, click the bright exit arrow; retrying the current room icon will not
  move the run forward.
- If arrows only pan the room map back and forth, remember that cycle and try
  the unvisited branch before returning to the previous arrow.
- If four or more consecutive turns are only minimap arrows, stop trusting the
  minimap arrow controls and click the matching path direction in the upper
  playfield itself.
- If both minimap arrows and upper-playfield path probes keep cycling, open
  settings first and look for a recovery, return, or other explicit progress
  control. The top run-menu button can open the external share panel instead,
  so use it only after settings is unavailable.
- If the external share panel opens, close it with **关闭分享面板**; treat the
  green **Tap** badge in the title as a non-action label.
- Hard loop observed on `2026-05-24`: after HP reached `0/55`, the visible
  minimap arrows only panned between views, upper-playfield path probes only
  panned the scene, the top run menu opened the external share panel, and
  settings **返回旅馆** produced only a transient banner without leaving the
  run. Treat this as a hard blocked state unless a new recovery control is
  discovered.
- If a treasure room has already been selected, take the treasure rather than hesitating.
- Choose **巨人之拳** / **Giant Fist** when offered as a treasure because it appears more offensive than defensive/utility options.
- Do not press generic **Confirm** before selecting the desired treasure; it accepts the current default selection.
- Choose **战斗专注** / **Battle Focus** over self-damage cards when learning cards because it sounds like a safer combat buff.
- If the card-learning screen offers **无限攻击**, **归一**, and **启动防守**,
  prefer **无限攻击** because it appears to be the most direct offensive card;
  never skip the offer with **Abandon**.
- If card descriptions cannot be read and **舍命一击** is one option, prefer
  a safer attack/buff card such as **闪耀挥击** or **战术准备** because
  `舍命` strongly implies a self-sacrifice or HP-cost effect.
- In combat, prefer safer visible cards such as **发现弱点**, **迅捷攻击**,
  **迅捷**, **转身准备**, or **弱点打击** before **End**. Avoid
  **舍命一击** when any safer card is playable.
- Choose **捡起** / **Pick Up** for weapons and combat gear because it supports the keep-fighting strategy.
- Choose **融合** on the weapon reward upgrade panel because it improves combat gear; do not treat the side-panel fusion shortcut as a fight action.
- Choose **融合** on combat-card reward upgrade panels because it improves fighting cards.
- Tap blank space to close reward popups after the reward is obtained.
- When the game offers multiple items/cards/treasures, inspect every option's description before choosing; do not press Confirm before the best item has been selected.
- In adventure events, prefer active/exploratory choices over passive leave/skip choices when neither option clearly costs health or resources.
- For `昏睡的吉他手`, prefer **拨弄他的吉他。** and avoid **他睡得好香，让他继续睡。** because the latter skips the encounter.
- Prefer **强化法阵** over **遗忘法阵** because strengthening improves the run while forgetting likely removes or downgrades a card/skill.
- Treat **Enhance Card** as a screen title, not a card choice; choose a visible card such as **战斗专注** instead.
- Treat **Forget Card** as a screen title, not a card choice; avoid forgetting cards unless no progression alternative exists.
- On the **Forget Card** screen, choose the return/back control instead of selecting a card to forget.
- If an external game sidebar or sharing panel opens, close it before continuing the tower.

## Automation Navigation Labels
- 下一房间
- 前进
- 上方道路
- 下方道路
- 左侧道路
- 右侧道路
- 右侧箭头

## Automation Navigation Keywords
- 道路
- 路线
- 箭头

## Automation Navigation Glyphs
- ↑
- ↓
- ←
- →

## Automation Command Labels
- 冒险
- 进入冒险
- 战斗
- 挑战
- 继续
- 恢复冒险
- 招募
- 招募冒险者
- 雇佣
- 领取
- 收集
- 捡起
- 强化
- 点击空白处关闭
- Return to Inn
- Recruit Adventurer
- Hire Adventurer
- Dismiss Reward
- Close Reward

## Automation Defeat Recovery Labels
- Return to Inn
- 返回旅馆

## Automation Recruit Labels
- Recruit
- Recruit Adventurer
- Hire
- Hire Adventurer
- 招募
- 招募冒险者
- 雇佣

## Automation Combat Double Tap Labels
- normal attack
- normal sword
- ordinary wooden sword
- shield
- focus gem
- battle focus
- blind blade
- find weakness
- swift attack
- swift
- turn preparation
- weakness strike
- life sacrifice strike
- 普通攻击
- 普通小剑
- 普通木剑
- 举盾
- 专注宝石
- 战斗专注
- 盲刃
- 发现弱点
- 迅捷攻击
- 迅捷
- 转身准备
- 弱点打击
- 舍命一击

## Automation Current Room Labels
- 幼虫
- 岩壳龙
- 大龙

## Item Choice Priorities
- Permanent stat changes are highest priority.
- Coin/gold gain is high priority, especially if it repeats per battle.
- Attack, damage, defense, HP/health, crit, and other stat increases are high priority when permanent or repeated per battle.
- Temporary one-battle effects are lower priority than permanent growth.
- Do not treat **消耗水晶** / crystal cost as bad by itself. Water crystals are
  purchase currency; evaluate the item effect first, and remember that stronger
  shop items can cost more crystals.
- Avoid item choices that cost, consume, or reduce HP/life/stats unless no better growth option exists.

## Known Item Effects
- Durable captured game information is ranked in `game_info.md`.

## Notes
- This file stores durable strategy only. Do not record transient screen state here.
