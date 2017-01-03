import sys
import time
import common
import random
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


def enter(g):
    # gift will have a delay
    time.sleep(2)
    # get gift before entering
    if g.click('gift'):
        time.sleep(3)
        g.click(center)
        return True
    return g.click(f)


def fight(g):
    g.screenshot()
    center = g.find('fight')
    if center:
        print 'try to click enemy'
        g.click(center)
        for i in xrange(2):
            x = random.uniform(-0.05, 0.05)
            y = random.uniform(-0.05, 0.05)
            g.click((center[0] + x, center[1] + y))
        return True
    return False


def move(g):
    print 'searching...'
    for i in xrange(3):
        time.sleep(2)
        g.click(right)
        g.screenshot()
        if g.click('boss') or fight(g):
            return True
    for i in xrange(3):
        time.sleep(1)
        g.click(left)
        g.screenshot()
        if g.click('boss') or fight(g):
            return True
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


def main():
    game = Game(create(), idle_time=20, debug=True)
    common.handle_common_interruption(game)
    game.addAction(common.finish(False))
    game.addAction(enter)
    game.addAction(SimpleAction('discover'))
    game.addAction(box)
    game.addAction(SimpleAction('boss'))
    game.addAction(fight)
    # game.addAction(common.select_enemy)
    game.addAction(isfighting)
    game.idle = move
    game.start()


if __name__ == "__main__":
    main()
