from __future__ import annotations

from game_driver.game_engine import GameEngine
from game_driver.v2.state import (
    GameStateV2,
    ScreenshotState,
    build_clickable_targets,
    screenshot_digest,
)


class GameEngineV2(GameEngine):
    """V2 engine surface layered on top of the stable v1 runtime."""

    def state_v2(self) -> GameStateV2:
        shot = ScreenshotState(
            image=self._screenshot,
            digest=screenshot_digest(self._screenshot),
        )
        targets = build_clickable_targets(self.text_locations)
        return GameStateV2(screenshot=shot, clickable_targets=targets)
