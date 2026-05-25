---
name: auto-play
description: Android game auto-play assistance using the repo's Android MCP screen/click tools and OCR-style button analysis. Use when Codex needs to inspect a live Android game screen, identify likely clickable buttons, recommend or execute a next tap, and maintain per-game Markdown strategy memory that describes how to play the game.
---

# Auto Play

## Workflow

Use `scripts/auto_play.py` from the repo root to run one auto-play turn through the Android MCP project at `projects/android_access_mcp`.

```bash
uv --directory skills/auto-play run python scripts/auto_play.py --game survivor --width 360 --height 800
```

Each turn:

- create a new turn folder under `skills/auto-play/games/<game>/turns/<turn-id>/`;
- prune old turn folders so only the latest 500 are kept by default;
- write the screenshot to that turn folder as `screenshot.png`;
- read that file with the skill-local OCR/clickability logic from
  `scripts/image_analyzer.py`;
- run a second detection pass using per-game cropped action templates from
  `skills/auto-play/games/<game>/images/`;
- read the per-game Markdown strategy at
  `skills/auto-play/games/<game>/strategy.md`;
- write OCR, ranked buttons, and decision data to `ocr.yaml` in the turn folder;
- decide the next move from strategy plus OCR candidates;
- when a confirm-style item/card/treasure choice is visible and auto-clicking is
  allowed, tap each visible item option to reveal its description, OCR and save
  the descriptions to `item_inspections.yaml`, select the best option, then
  confirm the choice;
- if OCR and template matching are insufficient, send the screenshot to the LLM
  using the prompt printed in the report;
- save the optional LLM response to `llm.yaml` in the same turn folder;
- regenerate `game_info.md` from item inspections and explicit LLM game-info
  captures so durable item, skill, and treasure facts are not lost when passing
  through detail screens;
- when the LLM finds an action or clickable icon that OCR/template matching
  missed, crop the LLM bbox and save it as a per-game template image for future
  turns;
- if choices are close, try the highest-scored option; use `--ask-on-ambiguous`
  only when the user explicitly wants to choose manually;
- if a move is clear and clicking is allowed, click through the Android MCP;
- after a click, take another live screenshot in memory and compare it with the
  pre-click screenshot using both full-screen similarity
  (`--state-similarity-threshold`, default `0.995`) and stable progress-region
  similarity (`--state-progress-similarity-threshold`, default `0.985`);
- for lower-half map/navigation clicks, verify the lower game UI changed so
  upper playfield animation does not count as progress by itself;
- save the final post-action screenshot as `last_screenshot.png` in the turn
  folder when a live post-action screenshot exists;
- if the screen still appears unchanged, sleep one second and retry the same tap
  up to `--state-change-retries` times (default `3`);
- if nothing changes, summarize the strategic lesson in the per-game Markdown
  strategy; add the action to "Ineffective Buttons" only when it is a
  high-confidence concrete action and not a preferred, fallback, confirm,
  combat, navigation, avoid, or noisy OCR label;
- when a clicked action is stuck/no-change, immediately run the OCR tuning
  report loop over a bounded recent window (`--ocr-tune-on-stuck-recent-turns`,
  default `10`; `--ocr-tune-on-stuck-iterations`, default `10`; per-iteration
  timeout `--ocr-tune-timeout`, default `60` seconds) and then keep playing with
  the failed action temporarily deprioritized;
- every 5 loop turns by default, compare the recent turn screenshots; if all
  are still similar, record an unblock lesson in strategy, temporarily
  deprioritize recent repeated actions when another candidate exists, run
  stuck-triggered OCR tuning, and keep the loop moving;
- every 50 loop turns by default, run 10 OCR tuning report iterations over the
  most recent 50 turn folders, then keep playing;
- write `metadata.yaml` with timestamp, worklog, LLM usage, action taken,
  strategy change recommendation, and last post-action screenshot path;
- sleep one second before the next turn.

Do not click by default. Add `--click-recommended` only when the user explicitly wants the skill to act on the device. Add `--loop` only after confirming the desired game and strategy.

## LLM Vision Fallback

When the report says `Decision status: needs_llm`, open the reported turn folder's `screenshot.png` and use the report's LLM prompt. The LLM response must be YAML with `objects` and `buttons`, including normalized clickable positions. Save that YAML to that same turn folder as `llm.yaml`, then rerun:

```bash
uv --directory skills/auto-play run python scripts/auto_play.py --game <game-name> --width 360 --height 800 --llm-result games/<game-name>/turns/<turn-id>/llm.yaml
```

After the LLM result is merged with OCR, run the strategy decision again. Close choices are tried in score order by default; if a tried action does not change the screen, the strategy records it as ineffective and a later turn can try the next choice.

Each LLM button should include a normalized bbox around the actionable visual
area and a `template_bbox` for the reusable image crop. The `template_bbox`
must contain exactly one clickable button/card/icon. Exclude neighboring cards,
adjacent buttons, unrelated labels, empty panel area, and duplicated UI.

```yaml
buttons:
  - label: Fight
    x: 0.50
    y: 0.82
    bbox:
      x1: 0.34
      y1: 0.77
      x2: 0.66
      y2: 0.87
    template_bbox:
      x1: 0.34
      y1: 0.77
      x2: 0.66
      y2: 0.87
    confidence: 0.9
    reason: Main progression button.
```

## Image Template Learning

Template images are durable game knowledge and should be committed with the
repo. They live under `skills/auto-play/games/<game>/images/`.

When an LLM button or clickable object/icon has a `template_bbox`, `crop_bbox`,
or `bbox` and no non-LLM candidate already captured the same label or nearby
coordinate, `auto_play.py` crops that LLM-provided one-button area from the turn
screenshot and saves it as `<label-slug>.png` or `<label-slug>--02.png` in the
game images folder. The cropper trusts `template_bbox` first, then `crop_bbox`,
then `bbox`, and applies a final focused trim around the LLM click center as a
safety net.
Future turns run two visual passes before asking the LLM:

- direct OCR/clickability extraction;
- image-template matching against every `.png` in the game's `images/` folder.

When asking the LLM for labels or descriptions, keep visible in-game names and
descriptions exactly as shown, including the original language. Do not translate
descriptions. Use a descriptive label only for non-text clickable icons that do
not show a usable original term, and do not store those labels as `game_info`.
If an item, skill, treasure, or card name and its effect text are visible in the
same screenshot, capture that name/effect pair in `game_info`; avoid storing
generic UI objects such as panels, maps, arrows, avatars, tabs, or prompts as
items.

This lets the skill remember what recurring action buttons look like without
putting transient screen state into the Markdown strategy. Commit useful learned
images; do not commit per-turn screenshots, OCR YAML, or tuning output.
The template label used as the button name is the filename slug before `--`,
preserving the visible game language. Hyphens are read as spaces only when the
captured label already uses hyphenated words. For example, `下一房间--02.png` is
reported as the button `下一房间`, so strategy files can reference `下一房间`.

### Template Audit And Dedup

Use `scripts/audit_templates.py` to review existing image templates, generate
LLM crop requests for suspicious images, and remove similar duplicates while
keeping the highest-quality crop.

```bash
uv --directory skills/auto-play run python scripts/audit_templates.py --game tower
```

To apply LLM-provided crop fixes, save a YAML file like this:

```yaml
crops:
  - path: 盲击.png
    template_bbox:
      x1: 0.0
      y1: 0.0
      x2: 0.9
      y2: 0.65
    reason: Keep only the single card button.
```

Then run:

```bash
uv --directory skills/auto-play run python scripts/audit_templates.py --game tower --llm-crops games/tower/template_crops.yaml --apply
```

`--apply` removes same-label duplicate templates when their visual similarity
is high enough, keeping the higher-quality image. Cross-label duplicates are
reported for review by default; pass `--dedupe-cross-label` only when the labels
truly describe the same reusable button.

## OCR Tuning Action

Use `scripts/tune_ocr.py` when the user wants to improve the "Ready actions captured from OCR" score. It treats saved LLM/action decisions as ground truth, regenerates OCR/template YAML from screenshots, and reports which needed action buttons are still missing.

Run the tuning action from the repo root:

```bash
uv --directory skills/auto-play run python scripts/tune_ocr.py --game tower --mode regenerate
```

Each iteration:

- read saved turns from `skills/auto-play/games/<game>/turns/`;
- identify actionable `ready` turns with a recommended or clicked action;
- regenerate OCR and learned template matches with the current
  `skills/auto-play/scripts/image_analyzer.py`;
- write generated per-turn OCR YAML under
  `skills/auto-play/games/<game>/ocr-tuning/<run>/turns/<turn>/ocr.yaml`;
- compute `ready_actions_captured_by_ocr / ready_actions`;
- refresh `skills/auto-play/games/<game>/game_info.md` from saved item
  inspections, explicit LLM game-info captures, and durable LLM object captures;
- summarize missing action clusters and symptoms in `summary.md`;
- use the printed "LLM Code Change Prompt" to make a small code change, usually
  in `skills/auto-play/scripts/image_analyzer.py`;
- rerun the same command and compare the score.

OCR tuning should not add generic OCR observations to `game_info.md`; only
durable captured names and descriptions belong there.

### Guarded Commit Loop

When tuning OCR code, only commit a change that increases `ready_actions_captured_by_ocr`.

1. Create a baseline report before editing OCR code:

```bash
uv --directory skills/auto-play run python scripts/tune_ocr.py --game tower --mode regenerate --run-name baseline
```

2. Make one small OCR code change, usually in `skills/auto-play/scripts/image_analyzer.py`.
3. Rerun with the baseline comparison:

```bash
uv --directory skills/auto-play run python scripts/tune_ocr.py --game tower --mode regenerate --baseline-report games/tower/ocr-tuning/baseline/report.yaml --fail-unless-improved
```

4. If the verdict is `improved`, create or switch to a `codex/` branch, stage only the OCR source/test/docs changes plus useful `strategy.md` and `images/` updates, and commit. Do not commit `skills/auto-play/games/<game>/ocr-tuning/` output.
5. If the verdict is `unchanged` or `regressed`, do not commit. Drop only the dirty OCR files changed during this attempt after checking the diff belongs to this attempt, summarize what the failed attempt taught, and try a different code change from the clean baseline.

Do not edit saved turn ground truth, strategy memory, or LLM YAML to improve the score. The tuning loop should improve OCR code, then prove the improvement by regenerated OCR YAML containing the needed action button by label or by near coordinate. For a fast non-OCR baseline over existing YAML, run:

```bash
uv --directory skills/auto-play run python scripts/tune_ocr.py --game tower --mode saved
```

## Strategy Memory

Treat the Markdown memory file as the game strategy, not the current run state. It should describe how to play the game across sessions. It contains:

- the game objective;
- preferred button labels and actions;
- avoided button labels and actions;
- ineffective button labels learned from no-change verification;
- decision rules;
- strategic notes learned from the user or from deliberate review.

Store strategy in the skill-local game folder and commit it:
`skills/auto-play/games/<game>/strategy.md`. Do not store transient screen
state, current counters, recent screenshots, button sightings, coordinates, or
run history as strategy memory. Before acting on a game, read its strategy file
if it exists. Prefer buttons listed in "Preferred buttons" and avoid labels
listed in "Avoid buttons". Users or agents may edit these Markdown lists
directly to teach the skill how to play a game.

Keep "Avoid buttons" conservative. Add a label there only when it is
high-confidence run-ending, clearly harmful, or explicitly rejected by the user.
Leave uncertain choices, weak OCR labels, and one-off no-change clicks in turn
metadata/worklogs until there is enough evidence to update a real strategy
section.

Keep "Ineffective buttons" conservative too. Add a label there only after
repeated, high-confidence evidence that a concrete action does not progress in
this game. Do not add OCR noise, stat text, start/confirm actions, useful combat
or card actions, navigation arrows, or context-dependent buttons after a single
failed click.

Store durable captured game information and rankings separately in
`skills/auto-play/games/<game>/game_info.md`. The script regenerates this
Markdown file every turn from saved item inspections and explicit LLM game-info
captures. It groups entries by type and sorts each group by the same
permanent-stat, coin, and per-battle-growth score used while choosing.

When the user chooses between multiple options, remember the durable strategic lesson, not the one-time screen state:

```bash
uv --directory skills/auto-play run python scripts/auto_play.py --game <game-name> --remember-choice "<label>" --choice-reason "<why this should be preferred>"
```

## Commands

Inspect only:

```bash
uv --directory skills/auto-play run python scripts/auto_play.py --game <game-name> --width 360 --height 800
```

Inspect and save extra debug images:

```bash
uv --directory skills/auto-play run python scripts/auto_play.py --game <game-name> --width 360 --height 800 --save-screen /tmp/screen.png --save-overlay /tmp/buttons.png
```

Turn folders are kept in `skills/auto-play/games/<game>/turns/`. The script keeps the newest 500 folders by default; change that with `--turn-history-limit`.

- `screenshot.png`
- `ocr.yaml`
- `metadata.yaml`
- `item_inspections.yaml` (only when item choices were inspected)
- `llm.yaml` (optional; only when an LLM fallback result is provided)
- `last_screenshot.png` (only when a live post-action screenshot exists)

Click the recommended button after analysis:

```bash
uv --directory skills/auto-play run python scripts/auto_play.py --game <game-name> --width 360 --height 800 --click-recommended
```

Click with a custom state-change threshold:

```bash
uv --directory skills/auto-play run python scripts/auto_play.py --game <game-name> --width 360 --height 800 --click-recommended --state-similarity-threshold 0.990 --state-change-retries 3
```

Loop clear turns, stopping when LLM or user input is needed:

```bash
uv --directory skills/auto-play run python scripts/auto_play.py --game <game-name> --width 360 --height 800 --click-recommended --loop --max-turns 20
```

Unblock checks compare the last 5 turn screenshots every 5 loop turns by
default. Tune that with `--unblock-check-interval`, `--unblock-window-size`, and
`--unblock-similarity-threshold`.

Periodic OCR tuning runs every 50 loop turns by default and evaluates the latest
50 turn folders 10 times through `scripts/tune_ocr.py --mode regenerate`. Tune
or disable that with `--ocr-tune-every-turns`, `--ocr-tune-recent-turns`, and
`--ocr-tune-iterations`.
