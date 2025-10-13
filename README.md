# Game Driver

## Setup
```
brew install android-platform-tools
```

## Interactive Notebook

Try the interactive Jupyter notebook:

```bash
# Launch Jupyter
uv run jupyter notebook notebooks/debug.ipynb
```

## Development
```bash
# Run example
uv run python script/survivor.py

# Run tests
uv run pytest

# Add dependencies
uv add requests

# Remove dependencies
uv remove requests
```
