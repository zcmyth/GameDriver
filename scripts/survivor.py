import logging
from game_driver import GameEngine
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger(__name__)


engine = GameEngine()

controls = [
    'activate',
    'confirm',
    'next',
    'start',
    'steamroll',
    # 'battle',
    # 'ok'
]

preferred_skills = [
    'destroyer',
    'drone',
]

secondary_skills = [
    'soccer',
    'havoc',
    'starforge',
    'palm wind',
    'hi-power',
    'drill',
    'twinborn',
]

max_iter = 9999999
for i in range(max_iter):
    time.sleep(2)
    print(f'Processing iteration: {i + 1}/{max_iter}')
    engine.refresh()

    if engine.contains('choice'):
        clicked, skill = engine.click_first_text(preferred_skills)
        if clicked:
            print('picked skill ' + skill)
            continue

        if engine.click_text('refresh', retry=3):
            print('clicked refresh')

        clicked, skill = engine.click_first_text(secondary_skills)
        if clicked:
            print('picked secondary skill ' + skill)
            continue
        print('pick a random skill')
        engine.click(288.0 / 460, 500.0 / 1024)
        continue

    control_clicked, control = engine.click_first_text(controls)
    if control_clicked:
        print(f'control {control} clicked')
        continue

    if engine.contains('back t'):
        engine.click(380.0 / 460, 280.0 / 1024)
        engine.click(0.5, 0.8, False)
        engine.click(230.0 / 460, 280.0 / 1024)
        engine.click(0.5, 0.8, False)
        engine.click(80.0 / 460, 280.0 / 1024)
        engine.click(0.5, 0.8, False)
        engine.click(46.0 / 460, 960.0 / 1024)
        engine.click_text('main challenge')
        engine.click(46.0 / 460, 960.0 / 1024)
        engine.click_text('main challenge')
        engine.click(380.0 / 460, 280.0 / 1024)
        continue

    if engine.contains('revival'):
        if engine.try_click_text('ad'):
            continue
        # engine.click(368.0 / 460, 380.0 / 1024)

    if i % 5 == 0:
        engine.click(0.5, 0.8, False)


print('Loop completed!')
