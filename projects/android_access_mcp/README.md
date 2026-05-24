# Android Access MCP

Minimal Python MCP stdio server for Android access through ADB.

It exposes three tools:

- `current_screen`: captures the current Android screen and returns PNG image content plus dimensions.
- `click`: clicks a coordinate. Values in `[0, 1]` are treated as normalized screen coordinates; larger values are treated as absolute pixels.
- `swipe`: swipes or drags from one coordinate to another. Values in `[0, 1]` are treated as normalized screen coordinates; larger values are treated as absolute pixels.

## Setup

ADB must be available and the Android device must be visible:

```bash
adb devices -l
```

The server uses `adbutils`, matching the parent `game_driver` project. If multiple devices are attached, it prefers a physical device over an emulator. You can force a serial with either `ANDROID_ACCESS_ADB_SERIAL` or `GD_ADB_SERIAL`.

## Run

From this directory:

```bash
uv run android-access-mcp
```

Or from the repository root:

```bash
uv --directory projects/android_access_mcp run android-access-mcp
```

Example Codex MCP config:

```json
{
  "mcpServers": {
    "android-access": {
      "command": "uv",
      "args": [
        "--directory",
        "/Users/chunzhang/game_driver/projects/android_access_mcp",
        "run",
        "android-access-mcp"
      ],
      "env": {
        "ANDROID_ACCESS_ADB_SERIAL": "optional-device-serial"
      }
    }
  }
}
```

## Tool Arguments

`current_screen` accepts:

- `max_height` (optional integer): resize the returned PNG to this height while preserving aspect ratio.
- `width` and `height` (optional integers): resize the returned PNG to an exact analysis size when both are provided.

`click` accepts:

- `x` (number, required): normalized or absolute x coordinate.
- `y` (number, required): normalized or absolute y coordinate.

`swipe` accepts:

- `start_x` (number, required): normalized or absolute starting x coordinate.
- `start_y` (number, required): normalized or absolute starting y coordinate.
- `end_x` (number, required): normalized or absolute ending x coordinate.
- `end_y` (number, required): normalized or absolute ending y coordinate.
- `duration_ms` (integer, optional): gesture duration in milliseconds. Defaults to `300`.
