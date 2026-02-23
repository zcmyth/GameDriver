from __future__ import annotations

import time

from game_driver.game_engine import GameEngine
from game_driver.v2.state import GameStateV2, ScreenshotState, _build_clickable_targets


class GameEngineV2(GameEngine):
    """V2 engine surface layered on top of the stable v1 runtime."""

    def state(self) -> GameStateV2:
        shot = ScreenshotState(
            image=self._screenshot,
        )
        targets = _build_clickable_targets(self.text_locations)
        return GameStateV2(screenshot=shot, clickable_targets=targets)

    def click(
        self,
        target: str,
        *,
        timeout_s: float = 5.0,
        poll_interval_s: float = 0.5,
        exact: bool = False,
        min_confidence: float = 0.0,
    ) -> bool:
        """Click a labeled target, waiting up to timeout for it to appear."""

        normalized = str(target).strip().lower()
        deadline = time.monotonic() + max(0.0, float(timeout_s))

        while True:
            state = self.state()
            candidates = [
                item
                for item in state.clickable_targets
                if item.confidence >= min_confidence
                and (
                    item.label.strip().lower() == normalized
                    if exact
                    else normalized in item.label.strip().lower()
                )
            ]
            if candidates:
                hit = candidates[0]
                super().click(hit.x, hit.y)
                return True

            if time.monotonic() >= deadline:
                return False

            if poll_interval_s > 0:
                time.sleep(poll_interval_s)
            self.refresh()
