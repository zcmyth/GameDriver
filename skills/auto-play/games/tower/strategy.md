# Auto Play Strategy: tower

## Objective
- Keep fighting and progress as far as possible through the tower.

## Preferred Buttons
- Adventure
- Enter Adventure
- Start Adventure
- Hard
- Hard Mode
- Dragon Forest
- 冒险
- 进入冒险
- 开始冒险
- 困难
- 困难模式
- 巨龙森林
- 龙之森林
- 龙森林
- 龙族森林
- 龙族森林 进入冒险
- 深渊森林
- 战斗
- 开战
- 挑战
- 幼虫
- 岩壳龙
- 大龙
- 侏儒怪
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
- 小丑飞刺
- 快速思考
- 虚弱
- 转身准备
- 弱点打击
- 专注宝石
- Chest
- Treasure
- 宝箱
- 前辈的宝物
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
- Continue Adventure
- 继续冒险
- Resume Adventure
- 恢复冒险
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
- SHOP
- Shop
- 商城
- .•.
- ...
- ⋯
- 快速冒险
- 我再想想
- 8$
- P.
- Recruit
- Recruit Adventurer
- 招募
- 招募冒险者
- Hire
- Hire Adventurer
- 雇佣
- Open settings
- Open run menu
- M1/6
- M2/6
- M3/6
- M4/6
- M5/6
- M6/6
- 1/6
- 2/6
- 3/6
- 4/6
- 5/6
- 6/6

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
- For this run, choose the Adventure path, choose **Hard** / **困难** difficulty,
  then choose **Dragon Forest** / **巨龙森林** / **龙之森林** before starting.
- On the stage loadout screen, click **开始冒险** / **Start Adventure** to begin
  the selected run.
- If character selection appears, pick any available character and continue;
  do not spend turns comparing characters unless one is clearly locked or
  unavailable.
- On the Dragon Forest character-selection screen, prefer **开始冒险** over
  **快速冒险** so the selected hard-mode stage is preserved.
- Prefer resume adventure when a previous tower fight can be continued.
- On a defeat screen (`游戏失败`), click **返回旅馆** / **Return to Inn** so the
  next run can start from the inn instead of tapping stat labels.
- The user explicitly said not to click **招募**; from the inn, choose
  **冒险** / fighting routes instead of recruiting or hiring.
- Prefer strength-building actions before navigation arrows: weapons, treasure, chest rooms, backpack/utility rooms, scroll/card rooms, combat cards, merge/upgrade actions, and reward pickups can improve the character.
- Use arrow/path controls only when there is no visible fight, reward, room choice, equipment, treasure, card, chest, backpack, merge, pickup, confirm-after-selection, or other strength-building action available.
- When choosing between items/cards/treasures, tap each option first to reveal and OCR its description, remember the description, then select the best option and confirm it.
- In item choices, always prefer permanent stat changes first, then coin gain, then stat increases that trigger per battle or every battle.
- Prefer items, skills, treasures, and event choices that increase money,
  coins, permanent stats, attack, health, defense, crit, or other direct combat
  stats.
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
- On the in-run room map, click the visible enemy icon such as **幼虫** or
  **侏儒怪** to start the encounter; do not treat its `Lv.1`/`Lv.2` label as the
  action.
- In treasure selection, prefer offensive fight-scaling options such as Giant Fist.
- In card learning, prefer combat focus or fight-scaling cards over cards that spend health.
- On card-learning screens (`选一张卡牌学习`), never click **Abandon**; select
  the best visible card first, then click **确定** / **Confirm**.
- On treasure selection screens, select the desired treasure card before pressing Confirm.
- Prefer actions that continue combat over reward collection when both are available.
- During combat, play visible attack, damage, shield, focus, or treasure-card
  buttons before ending the turn.
- During combat, prefer cards with visible attack/damage numbers at the bottom
  over shield, focus, setup, or other non-damage cards.
- During combat, attack several times in the same turn whenever possible:
  keep playing every affordable visible attack/damage card until no playable
  attack cards remain. Only then consider shield/utility cards, and click
  **End** only after all useful attacks for the turn are exhausted.
- **全力一击** is blocked while any defense card is still in hand. If it has a
  strong damage number and a defense card such as **守势** is visible, play or
  otherwise clear the defense card first, then use **全力一击** before ending.
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
- Do not treat standalone currency/stat text such as **8$**, **±2**, **+4**,
  or **+5** as an action; those are descriptive values, not buttons.
- Do not click floor/progress labels such as **M1/6** or **1/6**; they describe
  the current tower floor and do not move the run forward.
- When the last few turn screenshots remain nearly identical, temporarily deprioritize repeated actions and try a different visible target, tutorial-highlighted control, close/detail/back control, or vision-identified clickable before retrying.
- When a room arrow fails to change the screen after retries, pick the brighter route or a concrete room icon before retrying that arrow.

## Learned Choices
- The user said the tower strategy is to keep fighting.
- The user asked for Adventure -> hard mode -> Dragon Forest, then playing all
  levels with any character while prioritizing money and stat increases.
- On the Chinese adventure map, treat **深渊森林** as the requested forest
  route after hard mode is selected.
- On the hard-mode stage list, treat **龙族森林** as the requested Dragon Forest
  route and click its own **进入冒险** button, not the earlier stages.
- Choose **进入冒险** / **Enter Adventure** over the bottom Adventure tab when a selected stage is visible because it starts the selected tower fight.
- Choose **开始冒险** / **Start Adventure** on the stage loadout screen because it
  launches the selected fight.
- Choose **幼虫** on the first in-run map because it is the visible enemy room
  that starts the encounter; ignore the adjacent `Lv.1` text as a label.
- Choose **岩壳龙** on the in-run map when visible because it is another enemy
  room that starts an encounter; ignore its `Lv.1` label as a standalone action.
- Choose **大龙** on the in-run map when visible because it is a higher-level
  enemy room that starts an encounter; ignore its `Lv.2` label as a standalone action.
- Choose **侏儒怪** on the in-run map when visible because it is the next enemy
  room; ignore its `Lv.2` label as a standalone action.
- If a **Lv.2** enemy room is paired with a **休息点** / rest room on floor 1,
  take the rest first unless HP and deck strength are clearly overwhelming.
  A full-HP floor-1 hero still died to the Lv.2 frog after clearing nearby
  fights, so rest is the smarter path before harder optional combat.
- Choose **恢复冒险** / **Resume Adventure** instead of **放弃冒险** / **Abandon Adventure** because resuming keeps fighting.
- Choose **返回旅馆** / **Return to Inn** after defeat because it recovers to a
  playable state where the next tower attempt can begin.
- From the inn, choose **冒险** rather than **招募** because the user wants to go
  fighting immediately.
- Choose arrows only as fallback navigation when no better strength-building or event action is visible; improving the character is more valuable than blindly advancing.
- Choose **普通小剑** / **Normal Sword** when room choices appear because it is the fight-like route.
- On the branch map, the small up-arrow can highlight/shift focus without advancing; choose a concrete room icon instead.
- Choose treasure/chest rooms when no fight-like room is available because they can increase strength.
- Choose **前辈的宝物** over **职业背包** when both are visible because the treasure
  room is more likely to improve money, stats, or combat power.
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
- If both minimap arrows and upper-playfield path probes keep cycling, prefer
  a different visible path, concrete room icon, or exit direction before opening
  settings. Treat settings/run-menu controls as last-resort recovery, not normal
  navigation. The top run-menu button can open the external share panel, so use
  it only after path probes and settings are unavailable.
- On the **设置界面** settings overlay during a live run, click **继续冒险** to
  close the panel and keep the Dragon Forest run alive.
- If the dialog **Replace Old Adventure and Enter Tower?** appears, it is a
  simple confirmation prompt, not an item/card choice. Click **OK** directly and
  do not inspect or select **Cancel**.
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
- In combat, prefer safer visible cards such as **小丑飞刺**, **快速思考**,
  **虚弱**, **发现弱点**, **迅捷攻击**, **迅捷**, **转身准备**, or **弱点打击** before **End**. Avoid
  **舍命一击** when any safer card is playable.
- Treat bottom-number cards such as **归一**, **重影**, **撞击**, **普通攻击**,
  **普通木剑**, **弱点打击**, and **盲击** as direct attack cards. Spend the
  full energy bar playing these before setup cards when the enemy can be killed
  or pushed close to death.
- **发现弱点** is strongest when followed by **弱点打击** or other attacks in
  the same turn. Do not play **弱点打击** into an enemy with no visible
  vulnerability stacks unless no better attack exists.
- **战术准备** / **转身准备** select a card into hand; they do not immediately
  play that card. Use them only when enough energy remains to play the selected
  attack after confirming the selection.
- **战术准备** can open a discard-pile chooser. In lethal fights it is too slow
  unless there will still be enough energy to play the chosen finisher. Do not
  spend 3 energy on it when direct attacks can use the same energy immediately.
- Floor-5 elite **圆桌武士** is dangerous and can burst from mid HP to lethal in
  one enemy turn. Avoid this elite route if an alternate route reaches the
  stairs. If forced to fight it, skip slow first-turn gem setup unless the hand
  also contains immediate attacks or a guaranteed finisher.
- **弱点打击** is not always a one-shot. Against **圆桌武士**, with visible
  vulnerability stacks, it dealt only moderate damage. Use it after
  **发现弱点**, but still count remaining HP and keep enough energy for follow-up
  attacks.
- **归一II** is weak without hand/deck **重影** count; it dealt only 6 damage
  against **圆桌武士** when no `重影` was available. Prefer direct attacks or
  vulnerability setup if `归一` has no `重影` support.
- **强攻宝石** plus **骑士之盔** is still valuable because each physical card can
  raise physical attack sharply, but the damage shown on some attacks may remain
  low against evasive/elite enemies. Do not assume stat stacking alone has
  already solved the fight.
- **胜势II/III**, **强壮愿望**, and other physical-attack buffs are especially
  strong with **骑士之盔** / **骑士之誓** because every physical increase gets an
  extra physical-attack increase. In long fights, use these before big attacks
  such as **劈砍II**, **全力一击**, **归一**, and **神圣斩击**.
- Against enemies with repeated healing, do not rely on small unbuffed attacks.
  Stack physical attack first, then spend one turn playing multiple bottom-number
  attack cards. This beat floor-6 **乐子巫 Lv.5**, whose sustain kept restoring
  HP until physical attack reached about `298%`.
- **法力愿望** is a good utility card in long fights: observed cost 2 and gave
  `+4` mana, netting extra mana for more setup or follow-up attacks.
- **健康愿望** is a modest survival card: observed cost 2 and healed about `8`
  HP. Use it when HP is low and no lethal attack line is available.
- **强壮愿望** is a high-value buff card: observed cost 2 and raised physical
  attack by about `34%` when **骑士之誓** was active.
- **迅捷愿望** appears to be a speed/quickness buff, not a damage card. Play it
  after stronger physical buffs or attack-number cards unless spare mana would
  otherwise be wasted.
- **月光宝石** and **超越宝石** are setup cards. Use them mainly when the hand
  lacks good attack-number cards; direct damage and physical buffs are usually
  better when the enemy is near lethal.
- When **小丑飞刺** is visible with a damage number such as `19`, play it before
  defensive or utility cards because it directly helps finish the fight.
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
- If **卡牌使用记录** opens during combat, click **返回** to close it; do not
  treat OCR artifacts like **P.** near the top bar as combat actions.

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
- 开始冒险
- 战斗
- 挑战
- 继续
- 恢复冒险
- 领取
- 收集
- 捡起
- 强化
- 点击空白处关闭
- Return to Inn
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
- 小丑飞刺
- 快速思考
- 虚弱
- 转身准备
- 弱点打击
- 舍命一击
- 归一
- 重影
- 撞击
- 盲击
- 登龙斩
- 推击

## Automation Current Room Labels
- 幼虫
- 岩壳龙
- 大龙

## Automation Loadout Start Labels
- Start Adventure
- 开始冒险

## Automation Loadout Select Candidate
- 选择冒险者 | 0.23 | 0.60 | 2.0 | Select a visible adventurer card if Start Adventure does not progress from the loadout screen.

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
- **归一II**: upgraded burst attack; observed as cost 4, damage 6 plus extra
  damage per **重影** in hand, then discards those **重影** cards. High upgrade
  priority because it converts the duplicated **重影** engine into lethal burst.
- **重影**: cost 2 direct physical attack that adds another **重影** to the draw
  pile. Good cheap attack and synergy piece for **归一**.
- **普通木剑II/III**: reliable weapon attack; keep merging/upgrading when offered.
- **普通木剑II**: observed as a cost-2 direct attack that dealt `8` damage in
  the floor-6 witch fight after physical scaling. It also showed a focus/proc
  visual, so treat it as a useful cheap attack when mana is tight.
- **劈砍II**: high-value burst attack. In the floor-6 witch fight, it reached
  `41` displayed damage after physical scaling and was the best 4-cost damage
  card.
- **全力一击**: high-value 3-cost attack when usable. It reached `48` to `55`
  displayed damage after physical scaling, but it cannot be played while a
  defense card remains in hand.
- **无限攻击**: cost-1 attack that scales during the battle. It reached `23`
  displayed damage in the floor-6 witch fight and is excellent for spending the
  last 1 mana.
- **神圣斩击I/II**: use as a finisher when possible. A floor-6 kill with
  **神圣斩击** was followed by max HP increasing before the level-up screen.
- **巨人药水**: shop card, cost 0, consumable; description said it increases max
  HP by `600`. Use immediately if drawn in a boss or dangerous long fight.
- **净化药水**: shop card, cost 0, consumable; clears all own mark effects without
  triggering marks. Save/use it when the enemy applies dangerous debuffs.
- **骑士盾牌**: treasure; first combat round starts with `6` shield. Good but
  less important than offensive physical-scaling treasures.
- **赤铁巨斧III**: crystal-shop equipment; `物攻 +5`, `暴击 +3`. Good buy.
- **断刃匕首IV**: crystal-shop equipment; `速度 +1`, `物攻 +7`. Good buy.
- **发现弱点** + **弱点打击**: shop combo; **发现弱点** adds vulnerability, then
  **弱点打击** converts those stacks into direct damage.
- **骑士之盔**: treasure observed to add extra physical attack whenever combat
  physical attack increases. Strong offensive treasure.
- **愤怒宝石**: observed effect draws a physical attack from the draw pile when
  using a physical attack card. Good if active before a multi-attack turn.
- **怒火**, **舍命一击**, **舍命防守**, and **换血** can cost HP or imply
  self-damage. Avoid them unless healthy and they clearly create lethal damage.

## Notes
- This file stores durable strategy only. Do not record transient screen state here.
