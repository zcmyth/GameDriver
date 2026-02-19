# Game Driver

## Setup
```
brew install android-platform-tools
```

## Interaction Modes
The engine supports two explicit click modes:

1. **Text-based (OCR)**
   - `click_text(...)`
   - `click_first_text(...)`
   - `click_target("Start")` (routes to text)

2. **Image-based (template matching)**
   - `register_template(name, path)`
   - `register_templates_from_folder(path)`
   - `click_target("image:Start")` (routes to image click only)

Notes:
- `image:` prefix is explicit and fail-fast (no fallback to text).
- Folder-loaded template names can include source screen size using: `Name__1920x1080.png`.
  The matcher scales templates to current screen size before matching.

## Multi-game structure
- Core engine stays generic in `src/game_driver/` (`game_engine.py`, `device.py`, analyzers).
- Game-specific logic lives in `src/game_driver/games/` as strategy classes.
- Each game script in `scripts/` should only wire `GameEngine + Strategy + run_game_loop`.

To add a new game:
1. Create `src/game_driver/games/<game>.py` with a `<Game>Strategy.step(engine, i)` method.
2. Add a launcher script `scripts/<game>.py`.
3. Reuse the same generic engine and runner.

## Interactive Notebook

Try the interactive Jupyter notebook:

```bash
# Launch Jupyter
uv run jupyter notebook notebooks/debug.ipynb
```

## Development
```bash
# Run survivor automation
uv run python scripts/survivor.py

# Run tests
uv run pytest

# Add dependencies
uv add requests

# Remove dependencies
uv remove requests
```
