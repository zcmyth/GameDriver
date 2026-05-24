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
- prune old turn folders so only the latest 100 are kept by default;
- write the screenshot to that turn folder as `screenshot.png`;
- read that file with the skill-local OCR/clickability logic from
  `scripts/image_analyzer.py`;
- run a second detection pass using per-game cropped action templates from
  `skills/auto-play/games/<game>/images/`;
- read the per-game Markdown strategy at
  `skills/auto-play/games/<game>/strategy.md`;
- write OCR, ranked buttons, and decision data to `ocr.yaml` in the turn folder;
- decide the next move from strategy plus OCR candidates;
- if OCR and template matching are insufficient, send the screenshot to the LLM
  using the prompt printed in the report;
- save the optional LLM response to `llm.yaml` in the same turn folder;
- when the LLM finds an action that OCR/template matching missed, crop the LLM
  bbox and save it as a per-game template image for future turns;
- if choices are close, try the highest-scored option; use `--ask-on-ambiguous`
  only when the user explicitly wants to choose manually;
- if a move is clear and clicking is allowed, click through the Android MCP;
- after a click, take another live screenshot in memory and compare it with the
  pre-click screenshot using `--state-similarity-threshold` (default `0.995`);
- save the final post-action screenshot as `last_screenshot.png` in the turn
  folder when a live post-action screenshot exists;
- if the screen still appears unchanged, sleep one second and retry the same tap
  up to `--state-change-retries` times (default `3`);
- if nothing changes, summarize the strategic lesson in the per-game Markdown
  strategy, add the action to "Ineffective Buttons", and restart a turn when
  looping or when `--max-unchanged-restarts` allows it;
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
area:

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
    confidence: 0.9
    reason: Main progression button.
```

## Image Template Learning

Template images are durable game knowledge and should be committed with the
repo. They live under `skills/auto-play/games/<game>/images/`.

When an LLM button has a bbox and no non-LLM candidate already captured the same
label or nearby coordinate, `auto_play.py` crops that bbox from the turn
screenshot and saves it as `<label>--<turn-id>.png` in the game images folder.
Future turns run two visual passes before asking the LLM:

- direct OCR/clickability extraction;
- image-template matching against every `.png` in the game's `images/` folder.

This lets the skill remember what recurring action buttons look like without
putting transient screen state into the Markdown strategy. Commit useful learned
images; do not commit per-turn screenshots, OCR YAML, or tuning output.

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
- summarize missing action clusters and symptoms in `summary.md`;
- use the printed "LLM Code Change Prompt" to make a small code change, usually
  in `skills/auto-play/scripts/image_analyzer.py`;
- rerun the same command and compare the score.

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

Turn folders are kept in `skills/auto-play/games/<game>/turns/`. The script keeps the newest 100 folders by default; change that with `--turn-history-limit`.

- `screenshot.png`
- `ocr.yaml`
- `metadata.yaml`
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
