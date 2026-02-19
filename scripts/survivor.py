import json
import logging
import time
from collections import deque
from datetime import datetime
from pathlib import Path

from game_driver import GameEngine
from game_driver.games import SurvivorStrategy
from game_driver.runner import run_game_loop

ARTIFACTS = Path('artifacts')
LOG_PATH = ARTIFACTS / 'runner.log'
EVENTS_PATH = ARTIFACTS / 'events.jsonl'
ERRORS_DIR = ARTIFACTS / 'errors'


def _setup_logging():
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S',
    )

    file_handler = logging.FileHandler(LOG_PATH, mode='a', encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)


def _jsonl_append(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + '\n')


def _scene_hint(engine):
    locations = getattr(engine, '_locations', [])
    texts = [str(item.get('text', '')).lower() for item in locations]
    blob = ' '.join(texts)
    if 'choice' in blob:
        return 'skill_choice'
    if any(k in blob for k in ('mission', 'patrol', 'friends', 'start', 'daily event')):
        return 'home'
    if any(':' in t for t in texts) and any('lv.' in t for t in texts):
        return 'battle'
    if any(k in blob for k in ('buy', 'purchase', 'pack', 'offer')):
        return 'offer_popup'
    return 'unknown'


def _persist_error_artifacts(engine, iteration, error):
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    out = ERRORS_DIR / ts
    out.mkdir(parents=True, exist_ok=True)

    try:
        screenshot = getattr(engine, '_screenshot', None)
        if screenshot is not None:
            screenshot.save(out / 'screen.png')
    except Exception:
        logging.exception('Failed saving error screenshot')

    try:
        ocr = getattr(engine, '_locations', [])
        with (out / 'ocr.json').open('w', encoding='utf-8') as fh:
            json.dump(ocr, fh, ensure_ascii=False, indent=2)
    except Exception:
        logging.exception('Failed saving OCR dump')

    context = {
        'ts': datetime.now().isoformat(),
        'iter': iteration,
        'error': repr(error),
        'scene_hint': _scene_hint(engine),
        'metrics_snapshot': engine.metrics(),
    }
    with (out / 'context.json').open('w', encoding='utf-8') as fh:
        json.dump(context, fh, ensure_ascii=False, indent=2)


def _make_engine_listener(state):
    def listener(event, payload):
        mapped_action = None
        mapped_target = None
        success = None
        reason = None

        if event == 'click':
            mapped_action = 'tap'
            success = True
        elif event == 'text_click_success':
            mapped_action = 'text_click'
            mapped_target = payload.get('query')
            success = True
        elif event == 'text_click_miss':
            mapped_action = 'text_click'
            mapped_target = payload.get('query')
            success = False
            reason = 'no_match'
        elif event == 'template_click_success':
            mapped_action = 'template_click'
            mapped_target = payload.get('template')
            success = True
        elif event == 'template_click_miss':
            mapped_action = 'template_click'
            mapped_target = payload.get('template')
            success = False
            reason = 'no_match'

        event_row = {
            'ts': datetime.now().isoformat(),
            'event': event,
            'iter': state.get('iter', -1),
            'scene_hint': _scene_hint(state['engine']),
            'action': mapped_action,
            'target': mapped_target,
            'confidence': payload.get('confidence'),
            'x': payload.get('x'),
            'y': payload.get('y'),
            'success': success,
            'reason': reason,
            'metrics_snapshot': state['engine'].metrics(),
        }
        _jsonl_append(EVENTS_PATH, event_row)

    return listener


def main():
    _setup_logging()

    soft_restart_times = deque()

    while True:
        engine = GameEngine()
        strategy = SurvivorStrategy()
        state = {'iter': -1, 'engine': engine, 'consecutive_errors': 0}

        engine.add_listener(_make_engine_listener(state))

        def before_step(**kwargs):
            state['iter'] = kwargs.get('iteration', -1)

        def after_step(**kwargs):
            state['consecutive_errors'] = 0

        def on_error(**kwargs):
            iteration = kwargs.get('iteration', -1)
            error = kwargs.get('error')
            state['consecutive_errors'] += 1
            _persist_error_artifacts(engine, iteration, error)
            logging.error(
                'loop_error iter=%s consecutive_errors=%s error=%r',
                iteration,
                state['consecutive_errors'],
                error,
            )
            if state['consecutive_errors'] >= 3:
                raise RuntimeError('soft_restart_trigger: 3 consecutive loop errors')

        try:
            run_game_loop(
                engine,
                strategy,
                hooks={
                    'before_step': before_step,
                    'after_step': after_step,
                    'on_error': on_error,
                },
            )
        except Exception as exc:
            now = time.time()
            soft_restart_times.append(now)
            # Keep only last 10 minutes
            while soft_restart_times and (now - soft_restart_times[0]) > 600:
                soft_restart_times.popleft()

            logging.error(
                'Soft restart triggered (%d in last 10m): %r',
                len(soft_restart_times),
                exc,
            )

            if len(soft_restart_times) >= 3:
                logging.critical(
                    'ESCALATE_TO_MAIN: soft restart count reached 3 within 10 minutes'
                )
                raise SystemExit(2)

            time.sleep(2)
            continue


if __name__ == '__main__':
    main()
