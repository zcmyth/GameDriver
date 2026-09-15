# Auto Play Strategy: tower

## Objective
- Keep fighting and progress as far as possible through the tower.
- 每日流程可用 `--tower-daily` 持久化执行：深渊楼梯尽量到 124 层，回旅馆有次数则招募，再用新招募角色打尖塔木屋。

## 深渊速刷核心
- 硬门槛：生命优先堆到 250+，速度堆到 45+；低于门槛不提前跳层。成长宝物优先在 30 层前拿，30 层左右完成牌组后再跳层。
- 稳定无限流原则：启动后非临时牌不超过 7 张。三选一没有本职业核心牌时点 `放弃` 领取 10 金币，不为单卡强度污染牌库；`马上融合` 仍可拿。
- 开局必须先识别职业并刷对 `前辈的宝物`。旅行者首选 `毒龙匕首` 走直毒；连续 20 次真正重随仍未出现时，才接受 `花喇叭` 并立即切成纯祈愿，不得继续按毒流选牌。猎人接受 `远古魔法手套` / `贵族手刀`；法师先选 `电虫药水`，其次 `火焰草莓`；战士接受 `骑士狼牙棒` / `曜蓝水晶`。三选一要读取全部三列，目标在任意列都必须主动选中；同组出现多个目标时必须按写出的先后顺序选，不能同分后按屏幕位置取左。没有目标时先任选一件完成领取，在地图设置中 `返回旅馆`，关卡页点 `放弃冒险` 并确认，再重新进入深渊，确保随机结果真正刷新。
- 深渊当天展示的角色与职业固定；职业必须以实际起手牌识别，不能靠状态偏好在局内强切。职业偏好只负责跨重开筛选同一职业的前辈宝物，实战牌面一旦识别，应覆盖偏好。
- 旅行者根据启动宝物二选一，禁止混流。拿到 `毒龙匕首` 走七牌直毒：`无限宝石`、`剧毒晶石`、`黑神话`、`烈性毒药`、`涂毒小刀/毒药攻击`、`献祭`、`安乐毒药`，优先 `植物精华`，然后才是 `牛脾气/毒性思考`。战斗顺序为装备宝石 -> 回费过牌 -> 叠毒 -> `烈性毒药` 翻倍 -> `安乐毒药` 触发、回血并触发 `黑神话`。
- 拿到 `花喇叭` 或 `旅行者手册` 则走七牌纯祈愿：`无限宝石`、`天使`、`救赎`、`奉献`、`黑神话`、`献祭/未来汽水`、`回忆`。`花喇叭` 开战直接提供 5 层祈愿，先装备抽牌与回费宝石，再用 `天使` 指数放大，`救赎` 转为伤害与回复，`奉献` 的回复再触发 `黑神话` 补爆发。`牛脾气` 是首要天赋，用来保留原本会移除的 `天使`；`植物精华/毒性思考` 与本分支无关。每个功能槽只拿一张，升星优先 `天使`，然后 `救赎`。
- 旅行者尚未成型时的房间优先级：`卡牌遗忘` > `训练师` > `宝石牌包` > `职业牌包` > 生存/商店房。直毒训练师找 `植物精华/牛脾气/毒性思考`；纯祈愿只把 `牛脾气` 当硬核心，`不朽之心`可用于续航。
- 猎人速刷：`捕猎陷阱` 多多益善，`大力射击` 不超过陷阱的三分之一，`猎人嗅觉` 1-3 张；核心宝物 `魔法面具` + `火龙蛋` + `实验眼镜`，启动器从 `快速施法` / `双枪` / `魔法熊手` 三选一。7 月瞬发调整后用少量 `瞄准` 添加精准来加快破盾和斩杀；不要拿强攻宝石、虚无宝石或大量正面状态组件，它们会增加结算动画并拖慢速刷。2026-08 玩家实测连续三局约 25 分钟到 120 层，2026-09 又有新手第三天按这套通关的记录；职业可选时优先级高于旅行者。
- 法师速刷：首选 `电虫药水`，其每累计 5 层电击抽牌能同时补循环与输出。最新冰转电成型表为 `寒冷晶石×1 + 寒流×1 + 冷风×1 + 雷龙×1 + 电解冰×1 + 快速思考×2 + 小雷虫×2`；前三者先建立寒冷生成端，`电解冰` 转电击，`电虫药水` 再把电击换成过牌，`雷龙` 负责破嘲讽和补伤。`寒冰盾` 可作成型前的生存与寒冷过渡牌，`闪电晶石` 只是补强，不应挤掉上述核心槽位。只拿到 `电解冰` 而没有寒冷来源时，它暂时是死牌，奖励必须优先补生成端。免费魔术变牌出现 `路人甲` 时优先保留：实测可回复 2 生命、1 法力并抽 1，使用后移除，能同时补续航与压缩当回合牌库；`恢复宝石` 实测每次胜利回复 6 生命。遗忘房优先删除 `虚弱`、`能量飞弹`、`雷电飞弹`等基础杂牌，不删 `雷龙` 与上述寒冷、电击、抽牌和回血组件。拿到 `火焰草莓` 时改用公开验证的三卡极简火法，只留 `燃烧晶石` + `太阳盾` + `火焰打击`，依次使用后直接结算；它比寒冷转火长链更容易成型，也减少自动驾驶操作。
- `巨人协议` 是跨层容错件，不是输出核心；实战中一级可把 60 生命上限抬到 160，应该在抽到时尽早打出，避免低血才见牌来不及救场。它仍需配合休息/回血和本职业终结链，不能因为上限变厚就放弃爆发组件。
- 战士速刷：低要求默认走 2026-09 新公开的易伤无限链，`宝石手套` 开局安装 `超时空宝石`，用 `迅捷` 2-3 张过牌、`发现弱点` 2-3 张叠易伤、`弱点打击` 1 张结算，卡手时用 `未来汽水` 回蓝；宝物 `拐棍糖` 同时回蓝、抽牌、回血，`幻龙蛋` 复制超越牌防止断环。刷到 `曜蓝水晶` 可加入 `弱点加倍`，刷到完整 `魔法熊手/快速施法 + 女鹅套娃` 引擎时才考虑旧隐刀 `幽灵剑 + 换血`。
- 有红/橙面具时才切宇宙厚牌：法师保留并升满 `火焰连击/冰霜连击/闪电连击` 与 `雷龙` 中至少一条法术输出，其余法术牌和防御牌删除；随后大量拿牌但不升级，用面具按抽牌堆牌数造成两倍效果伤害。没有面具时禁止为了“宇宙”盲目撑厚。
- 通用必拿宝物：`实验眼睛`、`机械龙蛋`；早期可拿 `诅咒饭团`、`巨人泡泡糖`。不要拿 `宇宙十字架`，避免 123 层梦境零复制后反制本方。
- 121-123 层预留：`驱散药水` 1、`肉鸽药水` 1、`易伤药水` 1、`暴击药水` 1、元素药水 5+、`咖啡` 3；无攻击牌再留炸弹 3。123 层先用无用道具破三次模仿，再上肉鸽与负面印记。

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
- 深渊楼梯
- 进入下一层
- 战斗
- 开战
- 挑战
- 幼虫
- 岩壳龙
- 大龙
- 造地龙
- 进地龙
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
- BOSS战补给
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
- 好的
- 马上融合
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
- 观看
- 看广告
- 看广告复活
- 重试
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
- 即将发起战斗
- 返回
- 卡牌强化
- 木屋主人的水晶
- 水屋主人的水晶
- 生命商店
- 免费3次
- 点击【刷新】补货！
- 商品已售馨
- 哥布林水晶
- 胜利
- 哥布林钱袋
- 木屋主人的水
- 钱袋
- 本机
- 冒险中进入下一层时，获得10%金币利息
- 招募
- 变化法阵
- 旅行用品、
- 卡牌遗忘
- 设置
- 获得2点护盾，对敌方添加1层透支，移除

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
- For the current daily route, choose **深渊楼梯** directly from the Adventure
  map. Do not confuse its stage icon with the separate **困难模式** toggle.
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
- Daily-task runs may recruit from the inn after the Abyss Stairs attempt. Never
  sell or discard owned cards, treasures, equipment, collectibles, or characters.
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
- On card-learning screens (`选一张卡牌学习`), only take cards belonging to
  the current profession's speedrun core. If none qualifies, click **放弃** to
  receive 10 coins and keep the post-start deck at seven non-temporary cards or fewer.
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
- Ads are allowed. On a revive/ad prompt, prefer **观看** / **看广告复活** when it
  preserves the current run; after the ad, resume the interrupted adventure.
- If multiple fight-like actions are plausible, try the highest-scored option first.
- If an action does not change the screen after retries, try a different
  fight-like option on the next turn; only update Ineffective Buttons after
  repeated high-confidence evidence.
- Do not treat standalone currency/stat text such as **8$**, **±2**, **+4**,
  or **+5** as an action; those are descriptive values, not buttons.
- Do not click floor/progress labels such as **M1/6** or **1/6**; they describe
  the current tower floor and do not move the run forward.
- On the character-level-up popup, click **好的**. Never click stat transition
  text such as `101 >> 102`; those rows only describe the upgrade.
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
- For the daily sequence, finish the Abyss Stairs attempt first, recruit from
  the inn when a daily attempt remains, then enter Spire Cabin with the newly
  recruited adventurer.
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
- 旅行者短牌组尚未成型时，优先 **遗忘法阵/卡牌遗忘** 清理已确认的杂牌。直毒局保留毒核心，删 `救赎/慈悲/虔诚`；纯祈愿局保留 `天使/救赎/奉献`，先删 `灵魂燃烧/慈悲/毒药攻击/涂毒小刀/绿舌头`。任何分支都不删抽牌、回费与当前终结牌。
- Treat **Enhance Card** as a screen title, not a card choice; choose a visible card such as **战斗专注** instead.
- Treat **Forget Card/卡牌遗忘** as a screen title, then choose the highest-confidence known junk card and confirm **遗忘**; if every visible card is core or unreadable, return without deleting anything.
- If an external game sidebar or sharing panel opens, close it before continuing the tower.
- 每轮先检查 Android 前台包名。预期游戏包为 `cn.thearky.projectrl`；广告跳入 TapTap 或其他应用时只发送系统返回，不识别或点击外部内容；若落到系统桌面则只重新启动游戏包。TapTap 登录中间页只等待其自动回到游戏。
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

## Automation Prefer Watch Ads
- true

## Automation Passive Non-Action Labels
- 记录
- 设置
- 任务
- 融合
- 全服最高层数
- 当前所在层数
- 获得的战利品
- 冒险者携带的未激活宝物
- 当前层数
- 该层剩余冒险事件
- 正在进入旅馆
- 正在前往魔塔冒险

## Automation Reward Overlay Labels
- 恭喜获得

## Automation Reward Close Labels
- 点击空白处关闭

## 每日冒险资源纪律
- 绝不出售任何卡牌、宝物、装备、收藏品或其他物品；宁可跳过商店，也不要用出售换资源。
- 不要清空商店。只拿能直接完成爆发循环、提高续航，或让当前核心联动升级的少量牌。
- 不灭级宝物或物品最高优先；遇到时优先拿取，并在资源允许时优先激活或升级。
- 能融合或升级当前核心牌、核心宝物时优先升级；不要为了“以后可能有用”扩充无联动卡牌。
- 刷新是有限资源：单个商店默认最多刷新一次，金币或水晶紧张时不刷新；看见明确核心升级缺口时才刷新。
- 每次战斗出牌后手牌会重排，必须重新截图识别；不要连续点击旧坐标。
- 每日顺序由专门流程控制：先挑战深渊楼梯，再在旅馆有次数时招募，最后让刚招募的角色挑战尖塔木屋。通用按钮评分不得让招募抢在深渊楼梯之前。
- 选择卡牌时优先形成一个短链：稳定触发/抽牌或回费、爆发终结、必要回血。没有直接协同时宁可放弃奖励，避免牌组越来越慢。
- 地图上的“当前层数”和“剩余冒险事件”只是状态文字；必须选具体房间图标，不得点击计数文字。
- 看到“正在进入旅馆”或“正在前往魔塔冒险”时只等待加载，不点击提示文字。
- 尖塔房间处理完后，已访问的房间图标仍可能保留；优先点底部青色向下箭头离开，不重复访问同一房间。
- 尖塔终层优先 `强化法阵`，再拿 `BOSS战补给` 的 100% 最大生命恢复，然后挑战 Boss；默认跳过会扰乱核心牌的 `变化法阵`。
- 尖塔生命商店的免费奖励全部领取；显示 `商品已售馨` 后直接返回，不点击刷新提示，不消耗刷新资源。
- 击败尖塔 Boss 后，一看到 `冒险胜利` 就进入出口，选择 `马上离开（冒险者转正）`，不继续清理可选房间；结算页点击 `返回旅馆`。
- 尖塔短局可采用“宝石牌 + 晶体冥想 + 矮人手套 + 迅捷攻击”的低要求链：宝石供能并触发效果伤害，晶体冥想叠专注，迅捷攻击负责伤害与抽牌。优先强化抽牌和专注牌，确保循环与爆发同时增长。
- 2026-09-14 尖塔猎人实机通关链：前辈宝物 `骑士之刃`（使用物攻牌或法术牌时增加 8 点物攻）配合角色效果 `变异血统`（战斗中增加物攻时增加 5 点生命上限），让每次进攻同时成长输出和生存。牌序优先 `弹匣填装` 补弹并抽牌，`捕猎陷阱` 使用抽牌堆中的物攻牌，`快速拔枪` 连续使用 2 张物攻牌，`超时空宝石Ⅱ` 在移除牌时补抽；`恢复宝石` 负责层间回血。该局 Boss 生命 1256，满血补给后以 452 初始生命进入，成长至 492 生命上限并在第 5 回合击杀，无需复活。上一局泛用宝石战士两次生命均未击杀 Boss，说明尖塔短局应优先完整职业连锁，而不是堆互不兑现的泛用宝石。
- 2026-09-14 “抽一个、爬一个”法师实机：免费招募 `世故的双面人`，以前辈宝物 `魔法龙蛋`（使用非临时法术牌时复制进抽牌堆）起步，取得 `飞弹燃烧`、`燃烧火焰Ⅱ`、`燃烧宝石`、`冰霜飞弹`、`荆棘宝石`、`坚定宝石` 与 `暴击宝石Ⅱ`。该组合能靠法术复制和灼烧打过前五层，但缺少即时回蓝、稳定抽牌与层间回血，第六层战斗拖到第 10 回合后失败。结论：`魔法龙蛋` 只解决牌量，不解决费用、抽取和恢复；尖塔法师必须优先补至少一个回蓝/抽牌引擎，并在恢复位成形前避免继续拿纯伤害宝石。今日次数耗尽后直接停止，未购买次数。
- 深渊 124 层前必须先满足首回合生存门槛。若开局只有慢速毒/祈愿成长，没有立即护盾、回血或快速结算，宁可放弃无关强卡，集中补齐防御触发与爆发出口。

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
