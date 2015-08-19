from game import Game
from utils import rate_limited
from action import SingleClickAction

IMAGES = [
    'login',
    'login2',
    'ok',
    'close'
]


def startGhost(g):
    if g.clickImage('ghost'):
        for i in range(10):
            g.screenshot()
            if g.clickImage('begin_ghost'):
                break


@rate_limited(0.03, block=False)
def clickBeginGhost(g):
    g.clickImage('begin_ghost')


def main():
    game = Game()
    for image in IMAGES:
        game.addAction(SingleClickAction(image))
    game.addAction(startGhost)
    game.addAction(clickBeginGhost)
    game.start()


if __name__ == "__main__":
    main()
