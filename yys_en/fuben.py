import sys
import time
import common
import random
sys.path.append("..")

from game import Game
from action import SimpleAction
from devices import create


enemy = (0.757, 0.306)
center = (0.5, 0.5)
left = (0.1, 0.8)
right = (0.9, 0.8)


def move(g):
    print 'searching...'
    for i in xrange(4):
        time.sleep(2)
        g.click(right)
        g.screenshot()
        if g.click('boss') or fight(g):
            return True
    for i in xrange(6):
        time.sleep(1)
        g.click(left)
        g.screenshot()
        if g.click('boss') or fight(g):
            return True
    print 'cannot find target'
    exit()
    return False


def box(g):
    if g.click('box'):
        for i in xrange(2):
            time.sleep(1)
            g.click((0.1, 0.5))
        return True
    return False


def isfighting(g):
    return g.find('auto') is not None


def prepare(g):
    if g.find("can_prepare"):
        return g.click("prepare")
    return False


def fight(g):
    g.screenshot()
    center = g.find('fight')
    if center:
        print 'try to click enemy'
        g.click(center)
        return True
    return False


def main():
    game = Game(create(), idle_time=20, debug=True)
    common.handle_common_interruption(game)
    game.addAction(SimpleAction('ok'))
    game.addAction(common.finish(False))
    game.addAction(fight)
    game.addAction(box)
    game.addAction(SimpleAction('boss'))
    game.addAction(isfighting)
    game.idle = move
    game.start()


if __name__ == "__main__":
    main()
