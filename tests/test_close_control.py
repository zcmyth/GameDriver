from game_driver.close_control import try_click_close_control


class FakeEngine:
    def __init__(self, locations):
        self._locations = list(locations)
        self.clicked = []

    @property
    def text_locations(self):
        return list(self._locations)

    def click(self, x, y, wait=True):
        self.clicked.append((x, y, wait))

    def try_click_template(self, _template, threshold=0.88):
        return False


def test_close_control_prefers_corner_text_hit():
    engine = FakeEngine(
        [
            {'text': 'Close', 'confidence': 0.91, 'x': 0.5, 'y': 0.5},
            {'text': 'x', 'confidence': 0.9, 'x': 0.92, 'y': 0.08},
        ]
    )

    ok, reason = try_click_close_control(engine)

    assert ok is True
    assert reason == 'close_text_corner'
    assert engine.clicked[0][:2] == (0.92, 0.08)


def test_close_control_uses_safe_taps_when_no_hit_or_template():
    engine = FakeEngine([{'text': 'Mission', 'confidence': 0.95, 'x': 0.3, 'y': 0.8}])

    ok, reason = try_click_close_control(engine, icon_templates=('missing.png',))

    assert ok is True
    assert reason == 'close_safe_tap'
    assert engine.clicked[0][:2] == (0.92, 0.08)
    assert engine.clicked[1][:2] == (0.5, 0.1)
