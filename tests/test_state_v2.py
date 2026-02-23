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


class SequenceAnalyzer:
    def __init__(self, frames: list[list[dict[str, object]]]):
        self._frames = frames
        self._idx = 0

    def extract_text_locations(self, _image: object) -> list[dict[str, object]]:
        idx = min(self._idx, len(self._frames) - 1)
        self._idx += 1
        return list(self._frames[idx])


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


def test_v2_click_waits_until_target_appears() -> None:
    screenshot = Image.new('RGB', (100, 100), color='black')
    device = FakeDevice(screenshot)
    analyzer = SequenceAnalyzer(
        frames=[
            [],
            [
                {
                    'text': 'Start',
                    'x': 0.5,
                    'y': 0.7,
                    'confidence': 0.9,
                }
            ],
        ]
    )

    engine = GameEngineV2(device=device, analyzer=analyzer)

    ok = engine.click('start', timeout_s=1.0, poll_interval_s=0.0)

    assert ok is True
    assert len(device.clicks) == 1


def test_v2_click_times_out_when_target_missing() -> None:
    screenshot = Image.new('RGB', (100, 100), color='black')
    device = FakeDevice(screenshot)
    analyzer = SequenceAnalyzer(frames=[[]])

    engine = GameEngineV2(device=device, analyzer=analyzer)

    ok = engine.click('missing-target', timeout_s=0.0)

    assert ok is False
    assert device.clicks == []


def test_v2_click_any_clicks_when_one_target_appears() -> None:
    screenshot = Image.new('RGB', (100, 100), color='black')
    device = FakeDevice(screenshot)
    analyzer = SequenceAnalyzer(
        frames=[
            [],
            [
                {
                    'text': 'Patrol',
                    'x': 0.42,
                    'y': 0.66,
                    'confidence': 0.88,
                }
            ],
        ]
    )

    engine = GameEngineV2(device=device, analyzer=analyzer)

    ok = engine.click_any(['start', 'patrol', 'battle'], timeout_s=1.0, poll_interval_s=0.0)

    assert ok is True
    assert len(device.clicks) == 1


def test_v2_click_any_times_out_when_none_appear() -> None:
    screenshot = Image.new('RGB', (100, 100), color='black')
    device = FakeDevice(screenshot)
    analyzer = SequenceAnalyzer(frames=[[]])

    engine = GameEngineV2(device=device, analyzer=analyzer)

    ok = engine.click_any(['alpha', 'beta'], timeout_s=0.0)

    assert ok is False
    assert device.clicks == []


def test_v2_click_all_clicks_targets_sequentially() -> None:
    screenshot = Image.new('RGB', (100, 100), color='black')
    device = FakeDevice(screenshot)
    analyzer = SequenceAnalyzer(
        frames=[
            [{'text': 'Start', 'x': 0.2, 'y': 0.3, 'confidence': 0.9}],
            [{'text': 'Patrol', 'x': 0.7, 'y': 0.8, 'confidence': 0.92}],
        ]
    )

    engine = GameEngineV2(device=device, analyzer=analyzer)

    ok = engine.click_all(['start', 'patrol'], timeout_s=1.0, poll_interval_s=0.0)

    assert ok is True
    assert len(device.clicks) == 2


def test_v2_click_all_times_out_if_any_target_missing() -> None:
    screenshot = Image.new('RGB', (100, 100), color='black')
    device = FakeDevice(screenshot)
    analyzer = SequenceAnalyzer(
        frames=[
            [{'text': 'Start', 'x': 0.2, 'y': 0.3, 'confidence': 0.9}],
            [],
        ]
    )

    engine = GameEngineV2(device=device, analyzer=analyzer)

    ok = engine.click_all(['start', 'missing'], timeout_s=0.0)

    assert ok is False
    assert len(device.clicks) <= 1
