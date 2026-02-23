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

    def _find_matches(
        self,
        labels: list[str],
        *,
        exact: bool,
        min_confidence: float,
    ):
        normalized = [str(label).strip().lower() for label in labels if str(label).strip()]
        if not normalized:
            return []

        state = self.state()
        return [
            item
            for item in state.clickable_targets
            if item.confidence >= min_confidence
            and any(
                (
                    item.label.strip().lower() == needle
                    if exact
                    else needle in item.label.strip().lower()
                )
                for needle in normalized
            )
        ]

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

        return self.click_any(
            [target],
            timeout_s=timeout_s,
            poll_interval_s=poll_interval_s,
            exact=exact,
            min_confidence=min_confidence,
        )

    def click_any(
        self,
        targets: list[str],
        *,
        timeout_s: float = 5.0,
        poll_interval_s: float = 0.5,
        exact: bool = False,
        min_confidence: float = 0.0,
    ) -> bool:
        """Click the first available target from a list, or timeout."""

        deadline = time.monotonic() + max(0.0, float(timeout_s))

        while True:
            candidates = self._find_matches(
                targets,
                exact=exact,
                min_confidence=min_confidence,
            )
            if candidates:
                hit = candidates[0]
                super().click(hit.x, hit.y)
                return True

            if time.monotonic() >= deadline:
                return False

            if poll_interval_s > 0:
                time.sleep(poll_interval_s)
            self.refresh()
