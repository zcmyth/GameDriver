import logging
import re
import time
from datetime import datetime
from pathlib import Path

from game_driver import GameEngine

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger(__name__)


engine = GameEngine()
artifact_dir = Path('artifacts/stuck')
artifact_dir.mkdir(parents=True, exist_ok=True)

start_cooldown_until = -1

energy_actions = [
    'steamroll',
    'start',
    'battle',
]

free_controls = [
    'activate',
    'confirm',
    'next',
    'ok',
]

home_actions = [
    'view',
    'mission',
    'patrol',
    'challenge',
    'friends',
    'chest',
]

# Hard safety rule: never trigger purchasing flows.
blocked_texts = [
    'buy',
    'purchase',
    'shop',
    'buy now',
    'special offer',
    'limited time',
]

low_energy_texts = [
    'not enough energy',
    'insufficient energy',
    'need energy',
    'out of energy',
    'no energy',
]

preferred_skills = [
    'destroyer',
    'drone',
    # stats
    'atk',
    'all ammo',
     'duration',
    'hi-power',
    'energy',
    'bullet'
]

secondary_skills = [
    'havoc',
    'starforge',
    'palm',
    'soccer',
    'drill',
    'twinborn',
]


def _text_samples(engine):
    return [item['text'].lower() for item in engine._locations]


def _is_numeric_noise(text):
    # Examples seen in battle: 102M, 3.54B, 02:23, etc.
    return bool(re.fullmatch(r'[0-9:.xbmkn+\- ]{2,}', text.lower()))


def _contains_blocked_purchase_text(engine):
    return any(engine.contains(text, min_confidence=0.9) for text in blocked_texts)


def _contains_low_energy_text(engine):
    if any(engine.contains(text, min_confidence=0.85) for text in low_energy_texts):
        return True

    # OCR sometimes fragments full messages; keep a broad fallback.
    return engine.contains('energy', min_confidence=0.92)


def _run_low_energy_fallback(engine, i):
    # Prefer non-energy actions: dismiss dialogs and collect free progress.
    if engine.click_first_text(free_controls, min_confidence=0.9)[0]:
        return True

    if engine.try_click_text('ad', min_confidence=0.9):
        return True

    if engine.try_click_text('reward', min_confidence=0.88):
        return True

    if engine.try_click_text('claim', min_confidence=0.88):
        return True

    # Gentle exploration taps to find free tasks/menus without spending energy.
    if i % 6 == 0:
        engine.click(46.0 / 460, 960.0 / 1024, False)
        return True

    return False


def _is_in_battle(engine):
    texts = _text_samples(engine)
    if not texts:
        return False

    numeric_noise = sum(1 for text in texts if _is_numeric_noise(text))
    has_timer = any(':' in text for text in texts)
    has_level = any('lv.' in text for text in texts)

    # Live run evidence: battle screen has many numeric OCR artifacts.
    return (numeric_noise >= 8 and has_timer) or (numeric_noise >= 6 and has_level)


max_iter = 9999999
for i in range(max_iter):
    time.sleep(2)
    print(f'Processing iteration: {i + 1}/{max_iter}')
    engine.refresh()

    # Improvement guardrails: detect stuck loops + expose metrics each iteration window.
    if engine.is_stuck(repeat_threshold=8):
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        debug_path = artifact_dir / f'stuck_{ts}.png'
        engine.debug().save(debug_path)
        logger.warning(
            'Detected stuck state (same OCR signature repeatedly), '
            f'saved debug screenshot: {debug_path}, attempting recovery tap'
        )
        engine.click(0.5, 0.8, False)

    if i % 20 == 0:
        logger.info(f'engine metrics: {engine.metrics()}')

    low_energy_mode = _contains_low_energy_text(engine)
    if low_energy_mode:
        logger.info('Low energy detected; prioritizing free actions')
        if _run_low_energy_fallback(engine, i):
            continue

    # IMPORTANT: always handle actionable UI buttons before battle-mode heuristics.
    # Battle OCR noise can coexist with modal dialogs (e.g. reward popups with "next").
    if low_energy_mode:
        active_controls = list(free_controls)
    else:
        active_controls = list(free_controls + home_actions + energy_actions)

    # If START was recently clicked but screen did not progress, cool it down.
    if i < start_cooldown_until and 'start' in active_controls:
        active_controls.remove('start')

    if any(engine.contains(control, min_confidence=0.9) for control in active_controls):
        control_clicked, control = engine.click_first_text(
            active_controls,
            min_confidence=0.9,
        )
        if control_clicked:
            print(f'control {control} clicked')
            if control == 'start':
                # Avoid hammering START on home screen if it leads nowhere.
                start_cooldown_until = i + 8
            continue

    if _contains_blocked_purchase_text(engine):
        logger.warning('Purchase-like UI detected; trying to dismiss safely')
        # Non-buy dismissal path: back and neutral dismiss area only.
        engine.click(46.0 / 460, 960.0 / 1024, False)
        engine.click(0.5, 0.1, False)
        continue

    if engine.contains('choice', min_confidence=0.9):
        clicked, skill = engine.click_first_text(
            preferred_skills,
            min_confidence=0.9,
        )
        if clicked:
            print('picked skill ' + skill)
            continue

        if engine.click_text('refresh', retry=3, min_confidence=0.9):
            print('clicked refresh')

        clicked, skill = engine.click_first_text(
            secondary_skills,
            min_confidence=0.9,
        )
        if clicked:
            print('picked secondary skill ' + skill)
            continue
        print('pick a random skill')
        engine.click(288.0 / 460, 500.0 / 1024)
        continue

    if _is_in_battle(engine):
        # During active combat OCR is very noisy; avoid blind text clicks.
        # Keep movement/auto actions light and deterministic.
        if i % 3 == 0:
            engine.click(0.5, 0.82, False)
        if i % 9 == 0:
            engine.click(0.92, 0.86, False)
        continue

    if engine.contains('back t', min_confidence=0.9):
        engine.click(380.0 / 460, 280.0 / 1024)
        engine.click(0.5, 0.8, False)
        engine.click(230.0 / 460, 280.0 / 1024)
        engine.click(0.5, 0.8, False)
        engine.click(80.0 / 460, 280.0 / 1024)
        engine.click(0.5, 0.8, False)
        engine.click(46.0 / 460, 960.0 / 1024)
        engine.click_text('main challenge', min_confidence=0.9)
        engine.click(46.0 / 460, 960.0 / 1024)
        engine.click_text('main challenge', min_confidence=0.9)
        engine.click(380.0 / 460, 280.0 / 1024)
        continue

    if engine.contains('revival', min_confidence=0.9):
        if engine.try_click_text('ad', min_confidence=0.9):
            continue
        engine.click(368.0 / 460, 380.0 / 1024)

    if i % 5 == 0:
        engine.click(0.5, 0.8, False)


print('Loop completed!')
