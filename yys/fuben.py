import sys
import time
import common
sys.path.append("..")

from game import Game
from action import SimpleAction
from devices import create


f = '16'
if len(sys.argv) == 2:
    f = sys.argv.pop(1)

enemy = (0.757, 0.306)
center = (0.5, 0.5)
left = (0.2, 0.8)
right = (0.8, 0.8)


def fight(g):
    g.screenshot()
    if g.click('boss') or g.click('fight'):
        for i in xrange(3):
            g.screenshot()
            if g.find('auto'):
                for j in xrange(6):
                    g.click(enemy)
                    time.sleep(1)
                return True
            time.sleep(1)
        return True
    return False


def gift(g):
    if g.click('gift'):
        time.sleep(3)
        g.click(center)
        return True
    return False


def isfighting(g):
    return g.find('auto') is not None


def move(g):
    print 'searching...'
    for i in xrange(3):
        time.sleep(2)
        g.click(right)
        if fight(g):
            return True
    for i in xrange(3):
        time.sleep(1)
        g.click(left)
        if fight(g):
            return True
    return False


def box(g):
    if g.click('box'):
        for i in xrange(2):
            time.sleep(1)
            g.click((0.1, 0.5))
        return True
    return False


def main():
    game = Game(create(), idle_time=20, debug=True)
    common.handle_common_interruption(game)
    game.addAction(gift)
    game.addAction(SimpleAction('discover'))
    game.addAction(SimpleAction(f))
    game.addAction(box)
    game.addAction(fight)
    game.addAction(common.finish(False))
    game.addAction(isfighting)
    game.idle = move
    game.start()


if __name__ == "__main__":
    main()
