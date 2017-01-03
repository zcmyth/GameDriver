import sys
import time
import common
sys.path.append("..")

from game import Game
from action import SimpleAction
from devices import create


enemy = (0.757, 0.306)
any_point = (0.1, 0.1)


def finish(g):
    if g.click('failed'):
        for i in xrange(3):
            time.sleep(1)
            g.click(any_point)
        g.screenshot()
        if g.click('refresh'):
            time.sleep(1)
            g.screenshot()
            if g.click('ok'):
                return True
        exit()
    if g.click('finish1') or g.click('continue'):
        time.sleep(1)
        g.click(any_point)
        time.sleep(1)
        g.screenshot()
        return g.click('finish2')
    return False


def fight(g):
    if g.click('challenge'):
        while not g.click('prepare'):
            g.screenshot()
        while g.click('prepare'):
            g.screenshot()
        return True
    return False


def fighting(g):
    if g.find('auto'):
        g.click(enemy)
        return True
    return False


def tupo(g):
    if g.click('tupo2') or g.click('tupo1') or g.click('tupo'):
        time.sleep(2)
        g.screenshot()
        if not g.click('attack'):
            return False
        while not g.click('prepare'):
            g.screenshot()
        while g.click('prepare'):
            g.screenshot()
            g.click(enemy)
        return True
    return False


def main():
    game = Game(create(), idle_time=5, debug=True)
    common.handle_common_interruption(game)
    game.addAction(fighting)
    game.addAction(fight)
    game.addAction(finish)
    game.addAction(tupo)
    game.start()


if __name__ == "__main__":
    main()
