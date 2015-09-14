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
    if g.clickImage('task'):
        for i in range(3):
            g.screenshot()
            print 'try click ghost'
            if g.clickImage('ghost'):
                print 'clicked'


@rate_limited(0.03, block=False)
def clickBeginGhost(g):
    if g.clickImage('ghost'):
        print 'dumb ass move'


def main():
    game = Game()
    for image in IMAGES:
        game.addAction(SingleClickAction(image))
    game.addAction(startGhost)
    game.addAction(clickBeginGhost)
    game.start()


if __name__ == "__main__":
    main()
