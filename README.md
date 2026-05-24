# Game Driver

## Setup
```
brew install android-platform-tools
```

## Current Layout
The root `src/game_driver` package has been removed. Active Android automation
work now lives in independent repo-local projects and skills:

- `projects/android_access_mcp`: MCP server for Android screenshots and clicks.
- `skills/auto-play`: self-contained auto-play skill with its own Python
  project, OCR analyzer, game strategy memory, and learned action images.

Durable auto-play knowledge is stored per game under
`skills/auto-play/games/<game>/strategy.md` and
`skills/auto-play/games/<game>/images/`. Runtime turn history and OCR tuning
output stay local and ignored.

## Interactive Notebook

Try the interactive Jupyter notebook:

```bash
# Launch Jupyter
uv run jupyter notebook notebooks/debug.ipynb
```

## Agent Governance Docs
Canonical policy/config docs live in:
- `docs/agents/AGENT_WORKFLOW.md`
- `docs/agents/ARCHITECTURE_GUARDRAILS.md`
- `docs/agents/PR_GOVERNOR.md`
- `docs/agents/SURVIVOR_OPERATOR.md`

(Compatibility stubs are kept at repo root.)

## Development
```bash
# Run auto-play skill tests
uv --directory skills/auto-play run pytest tests

# Check auto-play skill lint and formatting
uv --directory skills/auto-play run ruff check .
uv --directory skills/auto-play run ruff format --check .

# Run Android MCP tests
uv --directory projects/android_access_mcp run --extra dev pytest tests

# Check Android MCP lint and formatting
uv run ruff check projects/android_access_mcp
uv run ruff format --check projects/android_access_mcp
```
