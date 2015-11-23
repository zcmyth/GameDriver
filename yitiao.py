from game import Game
from action import SimpleAction
import time
import utils
from devices import create

TASKS = [
    'mowang',
    'digua'
]


@utils.rate_limited(0.1, block=False)
def next(g):
    for task in TASKS:
        if g.click(task):
            time.sleep(3)
            return True
    return False


def choose(g):
    point = g.find('choose')
    if point:
        return g.click((point[0], point[1] + 80))
    return False


def main():
    game = Game(create())
    game.addAction(choose)
    game.addAction(next)
    for image in ['continue'] + utils.COMMON:
        game.addAction(SimpleAction(image))
    game.start()

if __name__ == "__main__":
    main()
