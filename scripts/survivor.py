import logging
import re
import time

from game_driver import GameEngine

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger(__name__)


engine = GameEngine()

controls = [
    'steamroll',
    'activate',
    'confirm',
    'next',
    'start',
    # 'battle',
    # 'ok'
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
        logger.warning(
            'Detected stuck state (same OCR signature repeatedly), '
            'attempting recovery tap'
        )
        engine.click(0.5, 0.8, False)

    if i % 20 == 0:
        logger.info(f'engine metrics: {engine.metrics()}')

    if _is_in_battle(engine):
        # During active combat OCR is very noisy; avoid blind text clicks.
        # Keep movement/auto actions light and deterministic.
        if i % 3 == 0:
            engine.click(0.5, 0.82, False)
        if i % 9 == 0:
            engine.click(0.92, 0.86, False)
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

    if any(engine.contains(control, min_confidence=0.9) for control in controls):
        control_clicked, control = engine.click_first_text(
            controls,
            min_confidence=0.9,
        )
        if control_clicked:
            print(f'control {control} clicked')
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
