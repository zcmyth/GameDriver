from game import Game
from utils import rate_limited, COMMON
from action import SimpleAction
from devices import create

IMAGES = COMMON + [
    'main',
    'continue'
]

ACTION = (1200, 230)


def task(g):
    point = g.find('choose')
    if point:
        return g.click((point[0], point[1] + 80))
    return False


@rate_limited(0.2, block=False)
def clickNext(g):
    g.click(ACTION)


def main():
    game = Game(create())
    game.addAction(task)
    for image in IMAGES:
        game.addAction(SimpleAction(image))
    game.addAction(clickNext)
    game.start()

if __name__ == "__main__":
    main()
