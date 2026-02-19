import time
from collections import deque

from game_driver.device import Device
from game_driver.image_analyzer import create_analyzer, draw_text_locations


class GameEngine:
    def __init__(self):
        self.device = Device()
        self.analyzer = create_analyzer()
        self._screenshot = None
        self._locations = []
        self._screen_signatures = deque(maxlen=12)
        self._metrics = {
            'refresh_count': 0,
            'click_count': 0,
            'text_click_attempts': 0,
            'text_click_success': 0,
            'text_click_miss': 0,
        }
        self.refresh()

    @staticmethod
    def _normalize_text(text):
        return str(text).strip().lower()

    def _screen_signature(self):
        texts = [self._normalize_text(item.get('text', '')) for item in self._locations]
        texts = [text for text in texts if text]
        texts.sort()
        return '|'.join(texts[:12])

    def refresh(self):
        self._screenshot = self.device.screenshot()
        self._locations = self.analyzer.extract_text_locations(self._screenshot)
        self._metrics['refresh_count'] += 1
        self._screen_signatures.append(self._screen_signature())

    def contains(self, text, exact=False, min_confidence=0.0):
        return bool(
            self.get_matched_locations(
                text,
                exact=exact,
                min_confidence=min_confidence,
            )
        )

    def get_matched_locations(self, text, exact=False, min_confidence=0.0):
        target = self._normalize_text(text)
        result = []
        for location in self._locations:
            if location.get('confidence', 0) < min_confidence:
                continue
            current_text = self._normalize_text(location['text'])
            if (exact and current_text == target) or (
                not exact and target in current_text
            ):
                result.append(location)
        # Prefer higher confidence first so we click the best OCR candidate.
        result.sort(key=lambda x: x.get('confidence', 0), reverse=True)
        return result

    def try_click_text(self, text, exact=False, min_confidence=0.0):
        self._metrics['text_click_attempts'] += 1
        matches = self.get_matched_locations(
            text,
            exact=exact,
            min_confidence=min_confidence,
        )
        if not matches:
            self._metrics['text_click_miss'] += 1
            return False

        # Click only the best match to avoid accidental multi-clicks.
        best = matches[0]
        self.click(best['x'], best['y'], wait=False)
        self.wait()
        self._metrics['text_click_success'] += 1
        return True

    def click_text(self, text, retry=5, exact=False, min_confidence=0.0):
        for _ in range(retry):
            if self.try_click_text(
                text,
                exact=exact,
                min_confidence=min_confidence,
            ):
                return True
            self.refresh()
        return False

    def click_first_text(self, text_list, exact=False, min_confidence=0.0):
        for text in text_list:
            if self.try_click_text(
                text,
                exact=exact,
                min_confidence=min_confidence,
            ):
                return True, text
        return False, None

    def wait_for_text(
        self,
        text,
        timeout=10,
        interval=1,
        exact=False,
        min_confidence=0.0,
    ):
        deadline = time.time() + timeout
        while time.time() < deadline:
            matched = bool(
                self.get_matched_locations(
                    text,
                    exact=exact,
                    min_confidence=min_confidence,
                )
            )
            if matched:
                return True
            time.sleep(interval)
            self.refresh()
        return False

    def click(self, x, y, wait=True):
        self._metrics['click_count'] += 1
        self.device.click(x, y)
        if wait:
            self.wait()

    def debug(self):
        return draw_text_locations(self._screenshot, self._locations)

    def is_stuck(self, repeat_threshold=8):
        if len(self._screen_signatures) < repeat_threshold:
            return False
        recent = list(self._screen_signatures)[-repeat_threshold:]
        return len(set(recent)) <= 1

    def metrics(self):
        attempts = self._metrics['text_click_attempts']
        success = self._metrics['text_click_success']
        success_rate = (success / attempts) if attempts else 0
        return {**self._metrics, 'text_click_success_rate': round(success_rate, 3)}

    def wait(self, seconds=1):
        time.sleep(seconds)
        self.refresh()
