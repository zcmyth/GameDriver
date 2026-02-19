import re
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

from game_driver.device import Device
from game_driver.image_analyzer import create_analyzer, draw_text_locations
from game_driver.template_matcher import TemplateMatcher


IMAGE_PREFIX = 'image:'


class ImageClickError(RuntimeError):
    pass


@dataclass(frozen=True)
class ClickRequest:
    raw_target: object
    mode: str
    target: object


class GameEngine:
    def __init__(
        self,
        device=None,
        analyzer=None,
        template_matcher=None,
        event_listeners=None,
        template_folder=None,
    ):
        self.device = device or Device()
        self.analyzer = analyzer or create_analyzer()
        self.template_matcher = template_matcher or TemplateMatcher()
        self._listeners = list(event_listeners or [])
        self._screenshot = None
        self._locations = []
        self._screen_signatures = deque(maxlen=12)
        self._attempt_samples = deque(maxlen=200)
        self._metrics = {
            'refresh_count': 0,
            'click_count': 0,
            'text_click_attempts': 0,
            'text_click_success': 0,
            'text_click_miss': 0,
            'template_click_attempts': 0,
            'template_click_success': 0,
            'template_click_miss': 0,
            'image_click_attempts': 0,
            'image_click_success': 0,
            'image_click_miss': 0,
            'engine_click_targets_until_changed_total': 0,
            'engine_click_targets_until_changed_success_total': 0,
            'engine_click_targets_until_changed_failed_total': 0,
        }
        if template_folder:
            self.register_templates_from_folder(template_folder)
        self.refresh()

    @staticmethod
    def _normalize_text(text):
        return str(text).strip().lower()

    @staticmethod
    def parse_click_target(target):
        if isinstance(target, str) and target.startswith(IMAGE_PREFIX):
            image_name = target[len(IMAGE_PREFIX) :].strip()
            if not image_name:
                raise ValueError('Image target cannot be empty. Use image:<name>.')
            return ClickRequest(raw_target=target, mode='image', target=image_name)
        return ClickRequest(raw_target=target, mode='text', target=target)

    def add_listener(self, listener: Callable[[str, dict], None]):
        self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[str, dict], None]):
        self._listeners = [item for item in self._listeners if item is not listener]

    def _emit(self, event, **payload):
        for listener in list(self._listeners):
            listener(event, payload)

    def _screen_signature(self):
        texts = [self._normalize_text(item.get('text', '')) for item in self._locations]
        texts = [text for text in texts if text]
        texts.sort()
        return '|'.join(texts[:12])

    def refresh(self):
        self._screenshot = self.device.screenshot()
        self._locations = self.analyzer.extract_text_locations(self._screenshot)
        self._metrics['refresh_count'] += 1
        signature = self._screen_signature()
        self._screen_signatures.append(signature)
        self._emit(
            'refresh',
            refresh_count=self._metrics['refresh_count'],
            location_count=len(self._locations),
            screen_signature=signature,
        )

    def _make_text_matcher(self, text_or_matcher, exact=False):
        if hasattr(text_or_matcher, 'search'):
            regex = text_or_matcher
            return lambda current_text: bool(regex.search(current_text))

        if callable(text_or_matcher):
            return text_or_matcher

        if isinstance(text_or_matcher, (list, tuple, set)):
            targets = {self._normalize_text(item) for item in text_or_matcher}
            if exact:
                return lambda current_text: current_text in targets
            return lambda current_text: any(
                target in current_text for target in targets
            )

        target = self._normalize_text(text_or_matcher)
        if exact:
            return lambda current_text: current_text == target
        return lambda current_text: target in current_text

    def contains(self, text, exact=False, min_confidence=0.0):
        return bool(
            self.get_matched_locations(
                text,
                exact=exact,
                min_confidence=min_confidence,
            )
        )

    def get_matched_locations(self, text, exact=False, min_confidence=0.0):
        matcher = self._make_text_matcher(text, exact=exact)
        result = []
        for location in self._locations:
            if location.get('confidence', 0) < min_confidence:
                continue
            current_text = self._normalize_text(location['text'])
            if matcher(current_text):
                result.append(location)
        # Prefer higher confidence first so we click the best OCR candidate.
        result.sort(key=lambda x: x.get('confidence', 0), reverse=True)
        return result

    def find_text_regex(self, pattern, flags=0, min_confidence=0.0):
        return self.get_matched_locations(
            re.compile(pattern, flags),
            min_confidence=min_confidence,
        )

    def try_click_text(self, text, exact=False, min_confidence=0.0):
        self._metrics['text_click_attempts'] += 1
        matches = self.get_matched_locations(
            text,
            exact=exact,
            min_confidence=min_confidence,
        )
        if not matches:
            self._metrics['text_click_miss'] += 1
            self._emit('text_click_miss', query=str(text))
            return False

        # Click only the best match to avoid accidental multi-clicks.
        best = matches[0]
        self.click(best['x'], best['y'], wait=False)
        self.wait()
        self._metrics['text_click_success'] += 1
        self._emit(
            'text_click_success',
            query=str(text),
            x=best['x'],
            y=best['y'],
            confidence=best.get('confidence', 0),
        )
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

    def click_target(
        self,
        target,
        retry=5,
        exact=False,
        min_confidence=0.0,
        threshold=0.88,
        **kwargs,
    ):
        request = self.parse_click_target(target)
        if request.mode == 'image':
            return self.click_image(request.target, retry=retry, threshold=threshold, **kwargs)
        return self.click_text(
            request.target,
            retry=retry,
            exact=exact,
            min_confidence=min_confidence,
        )

    def click_first_text(self, text_list, exact=False, min_confidence=0.0):
        for text in text_list:
            if self.try_click_text(
                text,
                exact=exact,
                min_confidence=min_confidence,
            ):
                return True, text
        return False, None

    def click_targets_until_changed(
        self,
        targets,
        *,
        min_confidence=0.85,
        exact=False,
        verify_wait_s=0.8,
        max_candidates_per_target=1,
        threshold=0.88,
    ):
        self._metrics['engine_click_targets_until_changed_total'] += 1
        attempts = 0
        details = []
        any_clicked = False

        def current_signature():
            recent = self.recent_signatures(1)
            return recent[-1] if recent else ''

        for target in targets:
            request = self.parse_click_target(target)
            if request.mode == 'image':
                match = self.get_template_match(request.target, threshold=threshold)
                attempts += 1
                if not match:
                    details.append(
                        {
                            'target': str(target),
                            'matched': False,
                            'clicked': False,
                            'state_changed': False,
                            'confidence': None,
                        }
                    )
                    self._emit(
                        'click_targets_until_changed_attempt',
                        target=str(target),
                        matched=False,
                        clicked=False,
                        state_changed=False,
                        confidence=None,
                    )
                    continue

                before_sig = current_signature()
                self.click(match['x'], match['y'], wait=False)
                any_clicked = True
                self.wait(verify_wait_s)
                after_sig = current_signature()
                changed = bool(before_sig and after_sig and before_sig != after_sig)
                confidence = match.get('confidence')
                details.append(
                    {
                        'target': str(target),
                        'matched': True,
                        'clicked': True,
                        'state_changed': changed,
                        'confidence': confidence,
                    }
                )
                self._emit(
                    'click_targets_until_changed_attempt',
                    target=str(target),
                    matched=True,
                    clicked=True,
                    state_changed=changed,
                    confidence=confidence,
                )
                if changed:
                    self._metrics['engine_click_targets_until_changed_success_total'] += 1
                    self._attempt_samples.append(attempts)
                    self._emit(
                        'click_targets_until_changed_result',
                        success=True,
                        clicked_target=str(target),
                        attempts=attempts,
                        changed=True,
                        reason='state_changed',
                    )
                    return {
                        'success': True,
                        'clicked_target': str(target),
                        'attempts': attempts,
                        'changed': True,
                        'reason': 'state_changed',
                        'details': details,
                    }
                continue

            matches = self.get_matched_locations(
                request.target,
                exact=exact,
                min_confidence=min_confidence,
            )
            candidates = matches[: max(1, int(max_candidates_per_target))]
            if not candidates:
                attempts += 1
                details.append(
                    {
                        'target': str(target),
                        'matched': False,
                        'clicked': False,
                        'state_changed': False,
                        'confidence': None,
                    }
                )
                self._emit(
                    'click_targets_until_changed_attempt',
                    target=str(target),
                    matched=False,
                    clicked=False,
                    state_changed=False,
                    confidence=None,
                )
                continue

            for candidate in candidates:
                attempts += 1
                before_sig = current_signature()
                self.click(candidate['x'], candidate['y'], wait=False)
                any_clicked = True
                self.wait(verify_wait_s)
                after_sig = current_signature()
                changed = bool(before_sig and after_sig and before_sig != after_sig)
                confidence = candidate.get('confidence')
                details.append(
                    {
                        'target': str(target),
                        'matched': True,
                        'clicked': True,
                        'state_changed': changed,
                        'confidence': confidence,
                    }
                )
                self._emit(
                    'click_targets_until_changed_attempt',
                    target=str(target),
                    matched=True,
                    clicked=True,
                    state_changed=changed,
                    confidence=confidence,
                )
                if changed:
                    self._metrics['engine_click_targets_until_changed_success_total'] += 1
                    self._attempt_samples.append(attempts)
                    self._emit(
                        'click_targets_until_changed_result',
                        success=True,
                        clicked_target=str(target),
                        attempts=attempts,
                        changed=True,
                        reason='state_changed',
                    )
                    return {
                        'success': True,
                        'clicked_target': str(target),
                        'attempts': attempts,
                        'changed': True,
                        'reason': 'state_changed',
                        'details': details,
                    }

        reason = 'no_state_change' if any_clicked else 'no_match'
        self._metrics['engine_click_targets_until_changed_failed_total'] += 1
        self._attempt_samples.append(attempts)
        self._emit(
            'click_targets_until_changed_result',
            success=False,
            clicked_target=None,
            attempts=attempts,
            changed=False,
            reason=reason,
        )
        return {
            'success': False,
            'clicked_target': None,
            'attempts': attempts,
            'changed': False,
            'reason': reason,
            'details': details,
        }

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

    def register_template(self, name, template_path):
        self.template_matcher.register_template(name, template_path)

    def register_templates_from_folder(self, folder_path):
        return self.template_matcher.register_from_folder(folder_path)

    def get_template_match(self, name_or_path, threshold=0.88, **kwargs):
        return self.template_matcher.match(
            self._screenshot,
            name_or_path,
            threshold=threshold,
            **kwargs,
        )

    def contains_template(self, name_or_path, threshold=0.88, **kwargs):
        return (
            self.get_template_match(name_or_path, threshold=threshold, **kwargs)
            is not None
        )

    def try_click_template(self, name_or_path, threshold=0.88, **kwargs):
        self._metrics['template_click_attempts'] += 1
        match = self.get_template_match(name_or_path, threshold=threshold, **kwargs)
        if not match:
            self._metrics['template_click_miss'] += 1
            self._emit('template_click_miss', template=str(name_or_path))
            return False

        self.click(match['x'], match['y'], wait=False)
        self.wait()
        self._metrics['template_click_success'] += 1
        self._emit(
            'template_click_success',
            template=str(name_or_path),
            x=match['x'],
            y=match['y'],
            confidence=match.get('confidence', 0),
        )
        return True

    def try_click_image(self, image_name, threshold=0.88, **kwargs):
        self._metrics['image_click_attempts'] += 1
        try:
            ok = self.try_click_template(image_name, threshold=threshold, **kwargs)
        except KeyError as exc:
            self._metrics['image_click_miss'] += 1
            raise ImageClickError(f'IMAGE_ASSET_NOT_FOUND: {image_name}') from exc

        if not ok:
            self._metrics['image_click_miss'] += 1
            raise ImageClickError(f'IMAGE_MATCH_LOW_CONFIDENCE: {image_name}')

        self._metrics['image_click_success'] += 1
        return True

    def click_image(self, image_name, retry=3, threshold=0.88, **kwargs):
        last_error = None
        for _ in range(retry):
            try:
                return self.try_click_image(image_name, threshold=threshold, **kwargs)
            except ImageClickError as exc:
                last_error = exc
                self.refresh()
        if last_error is not None:
            raise last_error
        raise ImageClickError(f'IMAGE_CLICK_FAILED: {image_name}')

    def click_template(self, name_or_path, threshold=0.88, retry=3, **kwargs):
        for _ in range(retry):
            if self.try_click_template(
                name_or_path,
                threshold=threshold,
                **kwargs,
            ):
                return True
            self.refresh()
        return False

    def click(self, x, y, wait=True):
        self._metrics['click_count'] += 1
        self.device.click(x, y)
        self._emit('click', x=x, y=y)
        if wait:
            self.wait()

    def debug(self):
        return draw_text_locations(self._screenshot, self._locations)

    def recent_signatures(self, count=None):
        signatures = list(self._screen_signatures)
        if count is None:
            return signatures
        return signatures[-count:]

    def is_stuck(self, repeat_threshold=8):
        if len(self._screen_signatures) < repeat_threshold:
            return False
        recent = list(self._screen_signatures)[-repeat_threshold:]
        return len(set(recent)) <= 1

    def is_cycle_stuck(self, cycle_len=2, min_cycles=3):
        if cycle_len <= 0 or min_cycles < 2:
            return False

        window = cycle_len * min_cycles
        if len(self._screen_signatures) < window:
            return False

        recent = list(self._screen_signatures)[-window:]
        pattern = recent[:cycle_len]

        # Ignore empty/noisy signatures; they are not reliable for cycle detection.
        if not all(pattern):
            return False

        # Require at least two distinct states in the cycle to avoid matching
        # simple static-screen stuck states (handled by is_stuck).
        if len(set(pattern)) < 2:
            return False

        for idx, sig in enumerate(recent):
            if sig != pattern[idx % cycle_len]:
                return False

        return True

    def metrics(self):
        attempts = self._metrics['text_click_attempts']
        success = self._metrics['text_click_success']
        success_rate = (success / attempts) if attempts else 0

        template_attempts = self._metrics['template_click_attempts']
        template_success = self._metrics['template_click_success']
        template_success_rate = (
            (template_success / template_attempts) if template_attempts else 0
        )

        image_attempts = self._metrics['image_click_attempts']
        image_success = self._metrics['image_click_success']
        image_success_rate = (image_success / image_attempts) if image_attempts else 0

        return {
            **self._metrics,
            'text_click_success_rate': round(success_rate, 3),
            'template_click_success_rate': round(template_success_rate, 3),
            'image_click_success_rate': round(image_success_rate, 3),
        }

    def wait(self, seconds=1):
        time.sleep(seconds)
        self.refresh()
