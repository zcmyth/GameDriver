from ..game import Game
from ..action import SimpleAction
from ..devices import create
import time
import utils
import sys

enemy = (969,220)
center = (640, 360)

def finish(g):
    if g.click('finish'):
        for i in xrange(2):
            time.sleep(2)
            g.click(center)
        return True
    return False

def fighting(g):
    if g.find('auto'):
        g.click(enemy)
        return True
    return False

def main():
    game = Game(create(), idle_time=10, debug=True)
    game.addAction(SimpleAction('ok'))
    game.addAction(SimpleAction('prepare'))
    game.addAction(finish)
    game.addAction(fighting)
    game.start()


if __name__ == "__main__":
    main()
