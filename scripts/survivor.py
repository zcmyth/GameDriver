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
    'starf',
    'staulorge',
    'stallorge',
    'havoc',
    'funnel',
    'fuluel',
    'vulcal',
    'beam gun',
    'damage up',
    'damageup',
]

secondary_skills = [
    'twin',
    'born',
    # stats
    'atk',
    'all ummo',
    'all ammo',
    'quel',
    # ball
    'ball',
    'shoe',
    # energycube
    'encgy',
    'supercell',
    'bullet',
    # overtime duration
    'duration',
    'duralion',
]

max_iter = 9999999
for i in range(max_iter):
    time.sleep(2)
    # logger.info(f'Processing iteration: {i + 1}/{max_iter}')
    engine.refresh()

    if engine.contains('choice'):
        clicked, skill = engine.click_first_text(preferred_skills)
        if clicked:
            logger.info('picked skill ' + skill)
            continue

        if engine.click_text('refresh', retry=3):
            logger.info('clicked refresh')

        clicked, skill = engine.click_first_text(secondary_skills)
        if clicked:
            logger.info('picked secondary skill ' + skill)
            continue
        logger.info('pick a random skill')
        engine.click(288.0 / 460, 500.0 / 1024)
        continue

    control_clicked, control = engine.click_first_text(controls)
    if control_clicked:
        logger.info(f'control {control} clicked')
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
