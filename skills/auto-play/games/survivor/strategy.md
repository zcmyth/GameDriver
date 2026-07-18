# Auto Play Strategy: survivor

## Objective
- Fight as much as possible and advance the account while never choosing ads.
- Current priority: clear Main Challenge entries before normal battle farming.

## Preferred Buttons
- Main Challenge
- Trial
- Path of Trials
- Confirm
- Close
- Drone
- Havoc
- Havo
- avo
- lavoc
- lova Havo
- Havoo
- avoc
- Starforge
- Starforg
- Steamroll
- Quick Battle
- Battle active skill
- Advance
- Continue
- Next
- Tap to Close
- Enter
- Play
- Claim
- Equip
- Upgrade
- Weapon
- Item
- Last Icon
- Last Challenge Icon
- Third column unclaimed row
- Scroll to higher challenge levels
- Back to
- Back to Home
- Back from main challenge
- Back from unavailable showdown

## Avoid Buttons
- Ad
- Ads
- Watch Ad
- Watch Ads
- Advertisement
- Google Play
- 1-tap buy
- Purchases are subject
- Family payment method
- Free With Ad
- Free
- Refresh
- Claimed
- Back to top
- 观看广告
- 看广告
- 广告
- 已领取

## Ineffective Buttons
- 259.Combat Lab
- Regular
- Regular Challenge
- Patrol
- Patrol Earnings
- Quick
- Earnings
- Normal Mode
- Hard Mode
- Nightmare Mode
- Refresh
- 313.Prologue Prison
- Not enough Energy
- Cleared
- Breeding Room
- Incubation Room
- Divine Fire Assault I
- Nezha
- COLLECT RESOURCES
- Dismiss assist pack popup
- Gems
- Tech Parts Crate
- Battle tab from shop
- Skip
- Revival
- Zombies Incoming
- Zombies Incoming!
- Skill Choice
- Select a skill to learn
- Select a skill t
- skill
- Select
- Select a
- ielec
- I to learn
- skill to learr
- skill to learn
- a skill to learn
- learn
- elect
- to learn
- EVO:
- vo
- Supplies
- Passage
- Gate
- Stele

## Fallback Buttons
- Back

## Decision Rules
- Prefer OCR-detected buttons and visible text for this game. Use learned image
  templates only when OCR repeatedly misses a real action.
- Do not click ads, ad reward buttons, or watch-ad prompts.
- When an **Announcement**, modal, or popup is visible and a real **Close**
  control is detected, close it before clicking underlying **Battle** /
  **Start** actions.
- When **Weekly Goodies** is visible, click **Claim** before any underlying
  **Battle** or **Start** controls.
- When a **Chapter Assist Pack** popup blocks the chapter screen and tapping
  outside has already failed, click **View** once to clear or route through the
  shop unlock flow, then return to the chapter screen and continue battle.
- When the shop opens from the assist pack flow, leave it via the bottom
  **Battle** tab instead of clicking shop items.
- If a Google Play purchase sheet appears, press Android Back immediately.
  Never click **1-tap buy** or payment controls.
- When a result screen shows **Victory**, **Congratulations!**, and **Confirm**,
  click **Confirm**. Do not click the title text or the battle active skill
  template on result screens.
- When a **Revival** popup appears with a plain **OK** button and no ad/watch
  wording, click **OK** before any underlying battle template. If ad/watch
  wording is visible, do not use that revive route.
- Do not click gray/greyed-out disabled buttons, even when OCR reads their text
  confidently.
- Treat survivor as three main modes:
  - **Battle screen**: use available **Steamroll** / **Battle** / **Fight** /
    **Start** actions when energy is sufficient.
  - **Main Challenge**: use the grid/back/re-enter rules below to advance.
  - **Actual battle**: the character is strong enough; prioritize staying
    unblocked and choosing visible skill/item cards over rerolling or waiting.
- While the current goal is clearing **Main Challenge**, prefer **Trial** /
  **Path of Trials** / **Main Challenge** before any home-screen **Steamroll**,
  **Battle**, **Fight**, or **Start** action. Only use **Steamroll** /
  **Battle** / **Fight** / **Start** after a Main Challenge chapter detail is
  open or an entered battle/result flow requires it.
- If actual battle repeats only **battle active skill** while the timer/boss
  state appears frozen, drag the movement joystick upward/toward the boss
  before continuing active-skill taps.
- If energy is sufficient, prefer **Steamroll** first, then **Battle** /
  **Fight** / **Start** actions. Do not treat **Start** as a preferred generic
  navigation action because **Regular Challenge** also exposes a **Start**
  button.
- If **Regular Challenge** is visible, leave via **Back to Home** instead of
  pressing **Start**. Regular Challenge is not the requested no-energy fallback;
  the fallback route is **Path of Trials** / **Main Challenge**.
- If energy is not sufficient or normal battle is blocked, go to **Trial** and
  **Main Challenge** to advance more.
- On the main challenge grid, clear levels in order. Prefer the lowest visible
  unclaimed level at or after the tracked `next_level`, then click its
  rightmost/third-column icon. Avoid **Claimed** / **已领取** cells.
- Target is clearing Main Challenge through level **330**. If all visible main
  challenge cells are **Claimed** and the tracked `next_level` is below 330,
  use short swipes to reveal that exact level instead of jumping to the
  deepest visible row.
- If all visible main challenge cells are **Claimed** near the current level
  range, click the bottom-left back button and re-enter **Main Challenge**;
  re-entry can refresh the grid so the new/current level appears on screen.
- When **Claimed** is visible, you are on the main challenge page. Click the
  bottom-left back button, then click **Main Challenge** again; this returns to
  the right level range.
- On the **Path of Trials** menu after backing out from **Claimed**, choose
  **Main Challenge** over **Survivor Showdown**, **Mega Challenge**, **Zone
  Operation**, or **Op Retreat**.
- If **Survivor Showdown** says matching has not started, use the bottom-left
  back button and return to **Main Challenge** instead of clicking **Start**.
- After re-entering **Main Challenge**, click the third column in the lowest
  visible row that does not have **Claimed** and matches the tracked next level.
- If re-entry still shows **Claimed** and OCR misses the next level number, but
  a centered level title is visible below the claimed row, treat that title as
  the next row and click its third-column icon instead of repeating
  back/re-enter.
- If OCR sees the tracked `next_level` is between two visible numbered rows but
  misses that row's number, infer the missing row from the surrounding row
  spacing and click its third-column icon. Never click the centered row title
  text itself.
- If back/re-enter repeats and the same claimed rows remain visible, click the
  low visible unclaimed row's third-column icon even when it is below the
  normal safe band. Example: after clearing Chapter 299, **300.Mirror Matrix**
  can remain near the bottom; click its third column rather than looping.
- If a Main Challenge row is partly hidden or ambiguous, do not scroll. Back
  out and re-enter **Main Challenge** so the current level is refreshed into a
  safely clickable position.
- Do not click **Back to top** while clearing levels 301-330; it jumps back to
  the earliest levels. Use short swipe-up or swipe-down scrolling to reveal the
  tracked `next_level` without skipping rows.
- Once a main challenge chapter detail is open and **Start** or **Battle** is
  visible, click that action instead of clicking another grid cell.
- In actual battle skill/item choice screens, capture every visible name and
  description into `game_info.md`, then choose the best currently ranked card.
  Do not click **Refresh** unless all visible choices are known bad or blocked.
- When choosing a skill card in actual battle, click the yellow title banner of
  the card, not the small red icon in the card body.
- If a skill description overlay opens on top of the skill-choice cards, close
  the overlay first. Do not keep clicking partial text fragments from the card
  hidden behind the overlay.
- If actual battle shows no text action, tap the bottom-right active skill
  button to keep the fight moving.
- Do not click top battle enemy/nameplate labels such as **Crystal Worm**,
  **Doommaker**, or **Nightmare Tulip**; treat them as passive HUD text and use
  the active skill or wait fallback instead.
- Verify active-skill progress against the main battle area, not the lower UI
  strip, because battle animation can leave the lower UI visually stable.
- If a survivor skill-card banner click does not change state, try another
  visible skill card or the actual-battle active skill button before marking
  the card ineffective.
- Capture visible weapon, item, skill, and equipment names and descriptions in
  `game_info.md` exactly as shown. Do not translate names or effects.
- When comparing weapons/items, wait for their description text and preserve it
  in `game_info.md`; priority will be supplied later by the user.
- If the active skill button does not verify progress, keep treating it as an actual-battle fallback because battle animation can leave the lower UI region visually stable.
- When the last few turn screenshots remain nearly identical, temporarily deprioritize repeated actions and try a different visible target, tutorial-highlighted control, close/detail/back control, or vision-identified clickable before retrying.

## Learned Choices
- The user said the goal is to fight as much as possible.
- The user said to prefer battle when energy is sufficient.
- The user said that when energy is not sufficient, use trial and main
  challenge to keep advancing.
- The user said that in main challenge, choose the last grid icon and avoid
  claimed rewards.
- The user asked to do normal battle with **Steamroll** until energy is empty;
  avoid starting **Regular Challenge** as the fallback route.
- The user said that when **Claimed** is visible, use bottom-left back, re-enter
  **Main Challenge**, then click the third column in the row that does not have
  **Claimed**.
- The user corrected the Main Challenge strategy: avoid scrolling the grid;
  back out and re-enter **Main Challenge** because that brings the new/current
  level onto the screen.
- The user said the back/re-enter trick restores the right main challenge level.
- The user said survivor has three main modes: the battle screen, the main
  challenge screen, and the actual battle. In actual battle, we are strong
  enough; focus on not getting blocked and on storing skills/items in
  `game_info.md` so ranking can improve later.
- The user asked to keep playing **Main Challenge** and try to clear all of the
  entries; this takes priority over normal energy battle farming.
- The current clearing goal is all levels through **330**, so the grid picker
  must not skip visible lower unclaimed levels just because a deeper row is
  clickable.

## Item Choice Priorities
- Always prefer any Drone option when it appears, including Type-A Drone,
  Type-B Drone, and Twinborn Drone variants.
- Always prefer Havoc and Starforge when they appear.
- Capture all weapons/items first. Do not invent priorities yet.
- Until the user gives rankings, prefer progression, combat power, weapons,
  upgrades, and durable stat/equipment improvements over temporary or ad-gated
  rewards.

## Known Item Effects
- Durable captured game information is ranked in `game_info.md`.

## Automation Noise Patterns
- ^\.\d+$
- ^\d+\.\d+$
- ^\d+\s*[x×]\s*\d+$
- ^\d+([.,]\d+)?[kmb]?\s+\d+([.,]\d+)?[kmb]+$
- ^\d+([.,]\d+)?\s*[-–]\s*\d+([.,]\d+)?[kmb][a-z]*$
- ^\.\d+([.,]\d+)?[kmb]{1,3}$
- ^\d+([.,]\d+)?[kmb]{1,3}$
- ^\d+([.,]\d+)?[kmb]{1,3}\.$
- ^\d+([.,]\d+)?[kmb]\d+([.,]\d+)?$
- ^\d+([.,]\d+)?[kmb]\d+([.,]\d+)?[kmb]\d*$
- ^\d+[A-Za-z]\s+(?:\d+\s+)*\d+[A-Za-z]$
- ^\d+[A-Za-z]:?[-–]?\s*[A-Za-z]?\s+\d+[A-Za-z]$
- ^\d+[A-Za-z]{2,}$
- ^[A-Za-z]{1,3}['’]\d+[A-Za-z]+$
- ^[\d.,]+['’]\s*\d+[A-Za-z]+$
- ^P[O0]{2}M$
- ^Refreshes left:\s*\d+$
- ^Refreshes left:*$
- ^Refreshes left:+$
- ^\d+([.,]\d+)?[a-z]$
- ^[,.:;]?\d+[A-Za-z]$
- ^[^A-Za-z0-9\s]\d+[A-Za-z]{1,3}$
- ^\d+[^A-Za-z0-9\s]\d+[A-Za-z]$
- ^[A-Za-z]\d+[.,]\d+[A-Za-z]$
- ^[A-Za-z]\d+[A-Za-z]$
- ^[A-Z]{1,3}\d+[A-Z]{1,3}$
- ^[A-Za-z]\d+(?:[A-Za-z]\d+)+[A-Za-z]?$
- ^[A-Za-z]\d+[A-Za-z]{2,}\d*$
- ^[^a-z0-9]?[a-z]?[x×]\s*\d+$
- ^\d+[A-Za-z]\s+\d+$
- ^\d+\s+\d+[A-Za-z]+$
- ^\d+(?:\s+\d+)+[A-Za-z*]+$
- ^\d+[A-Za-z]\s+\d+([.,]\d+)?[A-Za-z]+$
- ^[A-Za-z]?\.\d+[A-Za-z]$
- ^\.\d+[a-z]\d+$
- ^\.?\d+[A-Za-z]\d+[A-Za-z]+$
- ^\d+[A-Za-z]{2,}\d+[A-Za-z]+$
- ^\.?\d+[A-Za-z]\d+(?:[A-Za-z]\d+)+$
- ^(?:\d+[A-Za-z]\d+\s*)+$
- ^\d+\s+\d+[A-Za-z]\s+\d+(?:[.,]\d+)+$
- ^:\d{2}$
- ^\d{1,2}:\d{2}$
- ^\d{1,2}:\d{2}\.?$
- ^\d{1,2}:\d{2}\W*$
- ^\d{1,2}:\d{2}:$
- ^[\d.,]+[-–][\d.,]+$
- ^\d{1,3}[-–]\d+:?$
- ^\.?\d+[A-Za-z]\d+[A-Za-z]$
- ^\d+[A-Za-z]\d+[-–]\d+(?:[.,]\d+)?$
- ^\d+[A-Za-z]\s+\d+[A-Za-z]\s+[A-Za-z]?\d+[A-Za-z]$
- ^\d+(?:\s+[\d.,]+)+\.?$
- ^\d+\)$
- ^of$

## Automation Command Labels
- Steamroll
- Main Challenge
- Trial
- Path of Trials
- Survivor Showdown
- Mega Challenge
- Zone Operation
- Op Retreat
- Refresh
- Claimed
- Victory
- Congratulations!
- 已领取

## Automation Claimed Labels
- Claimed
- 已领取

## Automation Reward Overlay Labels
- Rewards

## Automation Reward Close Labels
- Tap to Close
- Tap anywhere to skip
- Anywhere to skip
- where to skip

## Automation Passive Non-Action Labels
- Dawnguard
- Dawnquard
- Dawnauard
- Shuttler
- Shuttle
- Center
- Cent
- Mission
- Mission Center
- Divine Sage
- Maple Phantom
- Maole Phantom
- New
- New!
- Boss Assault
- Zombies Incoming
- Zombies Incoming!
- Skill Choice
- Select a skill to learn
- Select a skill t
- skill
- Select
- Select a
- ielec
- I to learn
- skill to learr
- skill to learn
- a skill to learn
- learn
- elect
- to learn

## Automation Result Progress Labels
- Confirm
- Congratulations!
- Next
- Victory

## Automation Skill Choice Required Labels
- Skill Choice

## Automation Skill Choice Instruction Labels
- Select a skill to learn
- Skill Choice

## Automation Skill Choice Split Instruction Labels
- Select a + skill to learn

## Automation Skill Choice Ignored Labels
- Skill Choice
- Select a skill to learn
- New!
- New
- "New
- Select a skill t
- skill
- Select
- Select a
- ielec
- I to learn
- skill to learr
- skill to learn
- a skill to learn
- learn
- elect
- to learn
- ew
- ew!
- Nev
- lew
- lew!
- Ney
- Refresh

## Automation Level Row Patterns
- ^\s*\d{2,4}\s*[.．]\s*[A-Za-z]

## Automation Challenge Detail Action Labels
- Steamroll
- Quick Battle
- Start

## Automation Challenge Detail Patterns
- \bchapter\s+\d+\b
- ^\s*\d{2,4}\s*[.．]\s*

## Automation Recent Reentry Keywords
- Main Challenge

## Automation Waiting Required Text
- Survivor Showdown
- Survivor + Showdown

## Automation Waiting Hint Text
- Matching starts
- starts in
- season resets in

## Automation Shop Screen Required Text
- Daily Shop + Limited Chapter Assist Pack
- Daily Shop + Chapter 320 Assist

## Automation Safe Confirm Required Text
- Revival
- Oops, you're nearly there!

## Automation Shop Escape Candidate
- Battle tab from shop | 0.50 | 0.965 | 3.0 | Shop opened from the assist pack popup; return to the Battle tab and continue the chapter.

## Automation Energy Empty Labels
- Not enough Energy

## Automation Energy Empty Destination Labels
- Trial
- Main Challenge
- Path of Trials

## Automation Energy Empty Action Exemption Labels
- Chapter
- Rewards
- Info

## Automation Energy Empty Candidate
- Path of Trials | 0.74 | 0.95 | 3.2 | Energy is empty; open the Path of Trials tab instead of Regular Challenge.

## Automation Empty Screen Candidate
- Battle active skill | 0.86 | 0.79 | 2.6 | Actual battle has no text actions; tap the bottom-right active skill button to keep the fight moving.

## Automation Repeated Action Swipe Candidate
- battle active skill | 6 | Battle move toward boss | 0.22 | 0.78 | 0.22 | 0.48 | 3.4 | Repeated active-skill-only battle turns can stall on a boss; drag the joystick upward toward the boss.

## Automation Waiting Candidate
- Back from unavailable showdown | 0.08 | 0.965 | 3.0 | Showdown is visible but matching has not started; go back to Path of Trials and choose Main Challenge.

## Automation Claimed Back Candidate
- Back from main challenge | 0.08 | 0.965 | 3.0 | Claimed is visible on the main challenge page; go back and re-enter Main Challenge to return to the right level.

## Automation Third Column Unclaimed Row Candidate
- Third column unclaimed row | 0.83 | -0.11 | 3.0 | Main challenge grid is visible; click the rightmost unclaimed icon above the tracked next-level title.

## Automation Target Level
- 330

## Automation Disabled Visual Filters
- gray-disabled-buttons

## Automation Passive Nameplate Region
- 0.04 | 0.46 | 0.10 | 0.24 | 1.9

## Automation Main Screen Verification Labels
- Battle active skill

## Automation Always Preferred Choices
- Drone
- Twinborn Type-A
- Twinborn Type-B
- Type-A Drone
- Type-B Drone
- Havoc
- Havo
- lavoc
- lova Havo
- Havoo
- avoc
- Starforge
- Starforg

## Automation Item Preference Rules
- Max HP | 5 | survivor chapter clear: prefer survivability
- heal | 5 | survivor chapter clear: prefer survivability
- damage- | 5 | survivor chapter clear: prefer damage reduction
- received damage | 5 | survivor chapter clear: prefer damage reduction
- ATK | 4 | survivor chapter clear: prefer damage
- All attack CD | 4 | survivor chapter clear: prefer attack cooldown
- Firing interval | 4 | survivor chapter clear: prefer attack cooldown
- Oil Bond | -6 | survivor chapter clear: gold-only picks lose to combat or survival choices
- Oil Bone | -6 | survivor chapter clear: OCR variant of Oil Bond; gold-only picks lose to combat or survival choices
- Gold gain | -6 | survivor chapter clear: gold-only picks lose to combat or survival choices
- Item loot range | -3 | survivor chapter clear: loot range is lower priority than combat power

## Automation Ignored Game Info Types
- item

## Automation No Change Skill Choice Rule
- If a skill-card banner click does not change state, try another visible skill card or the actual-battle active skill button before marking the card ineffective.

## Automation No Change Empty Screen Rule
- If the active skill button does not verify progress, keep treating it as an actual-battle fallback because battle animation can leave the lower UI region visually stable.

## Notes
- This file stores durable strategy only. Do not record transient screen state
  here.
