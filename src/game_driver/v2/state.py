from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ClickableTarget:
    """Normalized clickable target detected on a frame."""

    id: str
    label: str
    x: float
    y: float
    confidence: float
    bbox: tuple[float, float, float, float] | None = None
    source: str = 'ocr'


@dataclass(frozen=True)
class ScreenshotState:
    """Screenshot payload captured for a game frame."""

    image: Any
    width: int | None = None
    height: int | None = None


@dataclass(frozen=True)
class GameStateV2:
    """Explicit v2 game state for deterministic runtime reasoning."""

    screenshot: ScreenshotState
    clickable_targets: tuple[ClickableTarget, ...]


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _build_clickable_targets(locations: list[dict[str, Any]]) -> tuple[ClickableTarget, ...]:
    """Convert analyzer locations into normalized clickable targets."""

    targets: list[ClickableTarget] = []
    for index, item in enumerate(locations):
        text = str(item.get('text', '')).strip()
        if not text:
            continue

        x = _clamp01(float(item.get('x', 0.0)))
        y = _clamp01(float(item.get('y', 0.0)))
        confidence = _clamp01(float(item.get('confidence', 0.0)))

        bbox = None
        if all(key in item for key in ('x1', 'y1', 'x2', 'y2')):
            bbox = (
                _clamp01(float(item['x1'])),
                _clamp01(float(item['y1'])),
                _clamp01(float(item['x2'])),
                _clamp01(float(item['y2'])),
            )

        target_id = f'ocr-{index}-{text.lower().replace(" ", "-")}'
        targets.append(
            ClickableTarget(
                id=target_id,
                label=text,
                x=x,
                y=y,
                confidence=confidence,
                bbox=bbox,
                source='ocr',
            )
        )

    targets.sort(key=lambda t: t.confidence, reverse=True)
    return tuple(targets)
