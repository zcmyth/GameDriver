import json
import re
from pathlib import Path

import pytest

from game_driver import game_engine as ge_module
from game_driver.v2.engine import GameEngineV2


class FakeDevice:
    def __init__(self, screenshot_bytes):
        self.clicks = []
        self._screenshot_bytes = screenshot_bytes

    def screenshot(self):
        return self._screenshot_bytes

    def click(self, x, y):
        self.clicks.append((x, y))


class FakeAnalyzer:
    def __init__(self, locations):
        self.locations = locations

    def extract_text_locations(self, _image):
        return list(self.locations)


@pytest.mark.parametrize(
    ('image_name', 'locations_name', 'expected_label_regexes'),
    [
        (
            'game_screen_v2.png',
            'state_v2_locations.json',
            [r'^Start$', r'^Patrol$'],
        ),
        (
            'game_screen_v2_steamroll_a.png',
            'state_v2_locations_steamroll.json',
            [r'^Steamroll Mode$', r'^Normal Mode$'],
        ),
        (
            'game_screen_v2_steamroll_b.png',
            'state_v2_locations_steamroll.json',
            [r'^Steamroll Mode$', r'^Normal Mode$'],
        ),
    ],
)
def test_state_v2_from_fixture_has_expected_clickable_targets(
    monkeypatch,
    image_name,
    locations_name,
    expected_label_regexes,
):
    fixture_dir = Path(__file__).parent / 'fixtures'
    fixture_path = fixture_dir / locations_name
    screenshot_path = fixture_dir / image_name

    locations = json.loads(fixture_path.read_text())
    screenshot_bytes = screenshot_path.read_bytes()

    fake_device = FakeDevice(screenshot_bytes)
    fake_analyzer = FakeAnalyzer(locations)

    monkeypatch.setattr(ge_module, 'Device', lambda: fake_device)
    monkeypatch.setattr(ge_module, 'create_analyzer', lambda: fake_analyzer)

    engine = GameEngineV2()
    state = engine.state_v2()

    assert state.screenshot.image == screenshot_bytes
    assert state.screenshot.digest

    labels = [target.label for target in state.clickable_targets]

    for pattern in expected_label_regexes:
        assert any(re.search(pattern, label) for label in labels), (
            f'Expected regex {pattern!r} to match one of labels {labels!r}'
        )

    for target in state.clickable_targets:
        assert 0.0 <= target.x <= 1.0
        assert 0.0 <= target.y <= 1.0
        assert 0.0 <= target.confidence <= 1.0
