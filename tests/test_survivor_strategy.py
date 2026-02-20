from game_driver.games import SurvivorStrategy


class FakeEngine:
    def __init__(self, locations):
        self._locations = locations
        self.clicked = []
        self._signatures = ['fake-signature']

    def is_stuck(self, repeat_threshold=8):
        return False

    def debug(self):
        class _Debug:
            @staticmethod
            def save(_path):
                return None

        return _Debug()

    def metrics(self):
        return {}

    def get_matched_locations(self, text, exact=False, min_confidence=0.0):
        matches = []
        is_regex = hasattr(text, 'search')
        target = None if is_regex else text.lower()

        for loc in self._locations:
            if loc.get('confidence', 0) < min_confidence:
                continue
            current = loc['text'].lower()

            if is_regex:
                if text.search(loc['text']):
                    matches.append(loc)
                continue

            if (exact and current == target) or (not exact and target in current):
                matches.append(loc)

        return sorted(matches, key=lambda x: x.get('confidence', 0), reverse=True)

    def contains(self, text, exact=False, min_confidence=0.0):
        return bool(
            self.get_matched_locations(
                text,
                exact=exact,
                min_confidence=min_confidence,
            )
        )

    def try_click_text(self, text, exact=False, min_confidence=0.0):
        matches = self.get_matched_locations(
            text,
            exact=exact,
            min_confidence=min_confidence,
        )
        if not matches:
            return False
        best = matches[0]
        self.click(best['x'], best['y'], wait=False)
        return True

    def click_first_text(self, text_list, exact=False, min_confidence=0.0):
        for text in text_list:
            if self.try_click_text(text, exact=exact, min_confidence=min_confidence):
                return True, text
        return False, None

    def click_text(self, text, retry=5, exact=False, min_confidence=0.0):
        return self.try_click_text(text, exact=exact, min_confidence=min_confidence)

    def click(self, x, y, wait=True):
        self.clicked.append((x, y))

    def try_click_template(self, _name_or_path, threshold=0.88):
        return False

    def recent_signatures(self, count=None):
        if count is None:
            return list(self._signatures)
        return self._signatures[-count:]

    def wait(self, seconds=1):
        return None

    def is_cycle_stuck(self, cycle_len=2, min_cycles=3):
        return False


def test_shop_label_does_not_trigger_purchase_dismiss_loop():
    engine = FakeEngine(
        [
            {'text': 'Start', 'confidence': 0.86, 'x': 0.15, 'y': 0.33},
            {'text': 'Part Assist Pack', 'confidence': 0.84, 'x': 0.5, 'y': 0.6},
            {'text': 'unlocked in Shop', 'confidence': 0.95, 'x': 0.6, 'y': 0.3},
            {'text': 'Mission', 'confidence': 0.88, 'x': 0.2, 'y': 0.8},
        ]
    )

    strategy = SurvivorStrategy()
    strategy.step(engine, i=1)

    # We should click a normal control (e.g., start/mission), not dismiss popup corners.
    assert engine.clicked
    assert (46.0 / 460, 960.0 / 1024) not in engine.clicked


def test_never_click_buy_text_even_if_visible():
    engine = FakeEngine(
        [
            {'text': 'Buy Now', 'confidence': 0.95, 'x': 0.5, 'y': 0.55},
            {'text': 'Daily Pack', 'confidence': 0.93, 'x': 0.5, 'y': 0.62},
        ]
    )

    strategy = SurvivorStrategy()
    strategy.step(engine, i=1)

    assert (0.5, 0.55) not in engine.clicked


def test_skill_choice_streak_breaker_triggers_alternate_recovery():
    engine = FakeEngine(
        [
            {'text': 'Choice', 'confidence': 0.96, 'x': 0.5, 'y': 0.1},
            {'text': 'Unrelated Text', 'confidence': 0.9, 'x': 0.2, 'y': 0.3},
        ]
    )

    strategy = SurvivorStrategy()

    for i in range(1, 7):
        strategy.step(engine, i=i)

    assert (46.0 / 460, 960.0 / 1024) in engine.clicked
    assert strategy.skill_choice_streak == 0


def test_skill_choice_fast_breaker_triggers_by_second_iteration():
    engine = FakeEngine(
        [
            {'text': 'Choice', 'confidence': 0.96, 'x': 0.5, 'y': 0.1},
            {'text': 'Unrelated Text', 'confidence': 0.9, 'x': 0.2, 'y': 0.3},
        ]
    )

    strategy = SurvivorStrategy()
    strategy.step(engine, i=1)
    strategy.step(engine, i=2)

    assert (46.0 / 460, 960.0 / 1024) in engine.clicked
    assert strategy.skill_choice_streak == 0


def test_skill_choice_prioritizes_hotspot_close_before_refresh_path():
    engine = FakeEngine(
        [
            {'text': 'Choice', 'confidence': 0.96, 'x': 0.5, 'y': 0.1},
            {'text': 'X', 'confidence': 0.97, 'x': 0.92, 'y': 0.08},
        ]
    )

    strategy = SurvivorStrategy()
    strategy.step(engine, i=1)

    assert engine.clicked
    assert engine.clicked[0] == (0.94, 0.07)


def test_skill_choice_disables_refresh_click_path():
    class RefreshTrackEngine(FakeEngine):
        def __init__(self, locations):
            super().__init__(locations)
            self.refresh_clicks = 0

        def click_text(self, text, retry=5, exact=False, min_confidence=0.0):
            if str(text).lower() == 'refresh':
                self.refresh_clicks += 1
            return False

    engine = RefreshTrackEngine(
        [
            {'text': 'Choice', 'confidence': 0.96, 'x': 0.5, 'y': 0.1},
            {'text': 'Refresh', 'confidence': 0.95, 'x': 0.5, 'y': 0.2},
            {'text': 'Noise', 'confidence': 0.90, 'x': 0.2, 'y': 0.3},
        ]
    )

    strategy = SurvivorStrategy()
    strategy.step(engine, i=1)

    assert engine.refresh_clicks == 0


def test_skill_choice_uses_hotspot_close_without_text_click_path():
    class HotspotChoiceEngine(FakeEngine):
        def click(self, x, y, wait=True):
            super().click(x, y, wait=wait)
            if x > 0.89 and y < 0.11:
                self._locations = []

    engine = HotspotChoiceEngine(
        [
            {'text': 'Choice', 'confidence': 0.96, 'x': 0.5, 'y': 0.1},
            {'text': 'Noise', 'confidence': 0.90, 'x': 0.2, 'y': 0.3},
        ]
    )

    strategy = SurvivorStrategy()
    strategy.step(engine, i=1)

    assert engine.clicked
    assert engine.clicked[0] == (0.94, 0.07)
