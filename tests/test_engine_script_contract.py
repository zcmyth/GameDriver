from game_driver import game_engine as ge_module
from game_driver.contracts import EngineRuntime
from game_driver.games.survivor import SurvivorStrategy


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


def test_game_engine_satisfies_engine_runtime_contract(monkeypatch):
    engine, _ = build_engine(monkeypatch, [])
    assert isinstance(engine, EngineRuntime)


def test_survivor_strategy_reads_text_locations_boundary(monkeypatch):
    engine, _ = build_engine(
        monkeypatch,
        [
            {'text': 'Mission', 'x': 0.5, 'y': 0.5, 'confidence': 0.9},
            {'text': 'Start', 'x': 0.6, 'y': 0.6, 'confidence': 0.92},
        ],
    )

    samples = SurvivorStrategy._text_samples(engine)
    assert samples == ['mission', 'start']


def test_text_locations_isolation_from_external_mutation(monkeypatch):
    engine, _ = build_engine(
        monkeypatch,
        [{'text': 'safe', 'x': 0.1, 'y': 0.2, 'confidence': 0.9}],
    )

    external = engine.text_locations
    external.clear()

    # engine internals should remain unchanged
    assert engine.contains('safe') is True
