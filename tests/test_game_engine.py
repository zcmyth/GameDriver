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


def build_engine(monkeypatch, locations):
    fake_device = FakeDevice()
    fake_analyzer = FakeAnalyzer(locations)

    monkeypatch.setattr(ge_module, 'Device', lambda: fake_device)
    monkeypatch.setattr(ge_module, 'create_analyzer', lambda: fake_analyzer)

    engine = ge_module.GameEngine()
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
