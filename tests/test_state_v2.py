import re
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from game_driver.v2.engine import GameEngineV2
from game_driver.image_analyzer import create_analyzer


class FakeDevice:
    def __init__(self, screenshot: Image.Image):
        self.clicks: list[tuple[float, float]] = []
        self._screenshot = screenshot

    def screenshot(self) -> Image.Image:
        return self._screenshot

    def click(self, x: float, y: float) -> None:
        self.clicks.append((x, y))


@pytest.mark.parametrize(
    ('image_name', 'min_clickables', 'expected_label_regexes'),
    [
        (
            'game_screen_v2.png',
            2,
            [r'^Start$', r'^Patrol$'],
        ),
        (
            'game_screen_v2_steamroll_a.png',
            2,
            [r'^(Steamroll|Steamroll Mode!?)$', r'^(Normal|Normal Mode)$'],
        ),
    ],
)
def test_state_v2_from_fixture_has_expected_clickable_targets(
    image_name: str,
    min_clickables: int,
    expected_label_regexes: list[str],
) -> None:
    fixture_dir = Path(__file__).parent / 'fixtures'
    screenshot_path = fixture_dir / image_name

    with Image.open(screenshot_path) as screenshot_image:
        screenshot = screenshot_image.convert('RGB')

    fake_device = FakeDevice(screenshot)
    analyzer: Any = create_analyzer()

    engine = GameEngineV2(device=fake_device, analyzer=analyzer)
    state = engine.state()

    labels = [target.label for target in state.clickable_targets]

    assert len(labels) >= min_clickables, (
        f'Expected at least {min_clickables} clickables, got {len(labels)}: {labels!r}'
    )

    for pattern in expected_label_regexes:
        assert any(re.search(pattern, label) for label in labels), (
            f'Expected regex {pattern!r} to match one of labels {labels!r}'
        )
