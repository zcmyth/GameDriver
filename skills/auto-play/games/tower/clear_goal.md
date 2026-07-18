# Tower Clear Goal

Objective: pass all 6 floors of the tower 10 times.

## Progress

- Verified full 6-floor clears: 0 / 10
- Current run: floor 6/6, level 8, last known HP 51/117, coins 39, crystals 1.
- Last known route state: floor-6 map after defeating 乐子巫 Lv.5, with BOSS宝库 and 超越牌包 visible.
- Machine-readable tracker: `clear_goal_state.yaml`.

## Resume Command

Once `adb devices` shows an attached device, run:

```bash
uv --directory skills/auto-play run python scripts/tower_clear_runner.py --target-clears 10 --max-turns 0 --click-recommended --wait-adb-seconds 120
```

## Counting Rule

Count a clear only when the game shows an end-of-run / full tower completion
state after floor 6, not when a single encounter shows `胜利`.

Do not increment the counter for:
- ordinary combat victory screens;
- level-up screens;
- shop, treasure, card-pack, or route-choice screens;
- reaching floor 6 without finishing the final boss/end state.

## Run Strategy Reminder

- Prefer attack-number cards and play several attacks per turn.
- Stack physical attack with 胜势 / 强壮愿望 before burst attacks.
- Clear defense cards before using 全力一击.
- Take healing/survival rewards before the final boss if HP is low.
