# Game Driver

## Setup
```
brew install android-platform-tools
```

## Interaction Modes
The engine now supports two ways to find click targets:

1. **Text-based (OCR)** via `click_text(...)`, `click_first_text(...)`
2. **Image-based (template matching)** via:
   - `register_template(name, path)`
   - `click_template(name_or_path, threshold=0.88, retry=3)`

Use template matching for icon-only UI elements (e.g. skull button, non-text tabs).

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
