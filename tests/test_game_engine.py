import re

import pytest

from game_driver import game_engine as ge_module


class FakeDevice:
    def __init__(self):
        self.clicks = []

    def screenshot(self):
        return object()

    def click(self, x, y):
        self.clicks.append((x, y))


class FakeAnalyzer:
    def __init__(self, locations):
        self.locations = locations

    def extract_text_locations(self, _image):
        return list(self.locations)


def build_engine(monkeypatch, locations, listeners=None):
    fake_device = FakeDevice()
    fake_analyzer = FakeAnalyzer(locations)

    monkeypatch.setattr(ge_module, 'Device', lambda: fake_device)
    monkeypatch.setattr(ge_module, 'create_analyzer', lambda: fake_analyzer)

    engine = ge_module.GameEngine(event_listeners=listeners)
    return engine, fake_device


def test_click_text_uses_highest_confidence_match(monkeypatch):
    engine, device = build_engine(
        monkeypatch,
        [
            {'text': 'confirm', 'x': 0.1, 'y': 0.2, 'confidence': 0.7},
            {'text': 'confirm', 'x': 0.8, 'y': 0.9, 'confidence': 0.95},
        ],
    )

    assert engine.click_text('confirm')
    assert device.clicks[0] == (0.8, 0.9)


def test_contains_returns_boolean(monkeypatch):
    engine, _device = build_engine(
        monkeypatch,
        [{'text': 'start game', 'x': 0.5, 'y': 0.5, 'confidence': 0.9}],
    )

    assert engine.contains('start') is True
    assert engine.contains('missing') is False


def test_metrics_track_click_success(monkeypatch):
    engine, _device = build_engine(
        monkeypatch,
        [{'text': 'activate', 'x': 0.5, 'y': 0.5, 'confidence': 0.9}],
    )

    assert engine.try_click_text('activate')
    assert not engine.try_click_text('missing')

    m = engine.metrics()
    assert m['text_click_attempts'] == 2
    assert m['text_click_success'] == 1
    assert m['text_click_miss'] == 1


def test_get_matched_locations_supports_regex(monkeypatch):
    engine, _device = build_engine(
        monkeypatch,
        [
            {'text': 'Tap to Start', 'x': 0.2, 'y': 0.2, 'confidence': 0.8},
            {'text': 'Settings', 'x': 0.8, 'y': 0.8, 'confidence': 0.95},
        ],
    )

    matches = engine.get_matched_locations(re.compile(r'tap\s+to\s+start'))
    assert len(matches) == 1
    assert matches[0]['text'] == 'Tap to Start'


def test_get_matched_locations_supports_callable(monkeypatch):
    engine, _device = build_engine(
        monkeypatch,
        [
            {'text': 'Play 1', 'x': 0.2, 'y': 0.2, 'confidence': 0.8},
            {'text': 'Play 99', 'x': 0.8, 'y': 0.8, 'confidence': 0.95},
        ],
    )

    matches = engine.get_matched_locations(lambda t: t.endswith('99'))
    assert len(matches) == 1
    assert matches[0]['text'] == 'Play 99'


def test_engine_event_listener_receives_click_events(monkeypatch):
    events = []

    def listener(event, payload):
        events.append((event, payload))

    engine, _device = build_engine(
        monkeypatch,
        [{'text': 'go', 'x': 0.5, 'y': 0.5, 'confidence': 0.9}],
        listeners=[listener],
    )

    engine.try_click_text('go')

    event_names = [name for name, _payload in events]
    assert 'click' in event_names
    assert 'text_click_success' in event_names


def test_click_target_routes_image_prefix_to_image_click(monkeypatch):
    engine, _device = build_engine(monkeypatch, [])

    called = {'image': None}

    def fake_click_image(name, retry=3, threshold=0.88, **kwargs):
        called['image'] = (name, retry, threshold)
        return True

    engine.click_image = fake_click_image

    assert engine.click_target('image:confirm', retry=2, threshold=0.91)
    assert called['image'] == ('confirm', 2, 0.91)


def test_click_target_image_prefix_fails_fast_without_fallback(monkeypatch):
    engine, _device = build_engine(
        monkeypatch,
        [{'text': 'confirm', 'x': 0.5, 'y': 0.5, 'confidence': 0.95}],
    )

    with pytest.raises(ge_module.ImageClickError):
        engine.click_target('image:missing', retry=1)


def test_click_targets_until_changed_returns_success_on_first_state_change(monkeypatch):
    engine, _device = build_engine(
        monkeypatch,
        [{'text': 'start', 'x': 0.5, 'y': 0.5, 'confidence': 0.95}],
    )

    signatures = ['s1']

    def fake_recent_signatures(count=None):
        data = list(signatures)
        if count is None:
            return data
        return data[-count:]

    def fake_wait(_seconds=1):
        signatures.append('s2')

    engine.recent_signatures = fake_recent_signatures
    engine.wait = fake_wait

    result = engine.click_targets_until_changed(['start'])
    assert result['success'] is True
    assert result['clicked_target'] == 'start'
    assert result['reason'] == 'state_changed'
    assert result['attempts'] == 1


def test_click_targets_until_changed_tries_next_target_after_no_change(monkeypatch):
    engine, _device = build_engine(
        monkeypatch,
        [
            {'text': 'alpha', 'x': 0.1, 'y': 0.2, 'confidence': 0.9},
            {'text': 'beta', 'x': 0.8, 'y': 0.9, 'confidence': 0.95},
        ],
    )

    signatures = ['s1']

    def fake_recent_signatures(count=None):
        data = list(signatures)
        if count is None:
            return data
        return data[-count:]

    wait_calls = {'n': 0}

    def fake_wait(_seconds=1):
        wait_calls['n'] += 1
        if wait_calls['n'] == 1:
            signatures.append('s1')
        else:
            signatures.append('s2')

    engine.recent_signatures = fake_recent_signatures
    engine.wait = fake_wait

    result = engine.click_targets_until_changed(['alpha', 'beta'])
    assert result['success'] is True
    assert result['clicked_target'] == 'beta'
    assert result['attempts'] == 2


def test_click_targets_until_changed_returns_no_match(monkeypatch):
    engine, _device = build_engine(monkeypatch, [])
    result = engine.click_targets_until_changed(['missing'])

    assert result['success'] is False
    assert result['reason'] == 'no_match'
    assert result['attempts'] == 0


def test_click_targets_until_changed_returns_no_state_change(monkeypatch):
    engine, _device = build_engine(
        monkeypatch,
        [{'text': 'start', 'x': 0.5, 'y': 0.5, 'confidence': 0.95}],
    )

    signatures = ['s1']

    def fake_recent_signatures(count=None):
        data = list(signatures)
        if count is None:
            return data
        return data[-count:]

    def fake_wait(_seconds=1):
        signatures.append('s1')

    engine.recent_signatures = fake_recent_signatures
    engine.wait = fake_wait

    result = engine.click_targets_until_changed(['start'])
    assert result['success'] is False
    assert result['reason'] == 'no_state_change'
    assert result['attempts'] == 1
