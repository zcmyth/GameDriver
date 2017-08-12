import sys
import common
import time

sys.path.append("..")
from game import Game
from action import SimpleAction
from devices import create


def prepare(g):
    if g.find("can_prepare"):
        return g.click("prepare")
    return False


def box(g):
    if g.click('box'):
        for i in xrange(2):
            time.sleep(1)
            g.click((0.1, 0.5))
        return True
    return False

def double_yuhun(g):
    if g.click("double_yuhun"):
        time.sleep(5)
        g.screenshot()
        return g.click("double_yuhun")
    return False


def main():
    game = Game(create(rate_limit=2, blur=0.005), debug=True)
    game.addAction(SimpleAction('accept1'))
    game.addAction(SimpleAction('accept2'))
    common.handle_common_interruption(game)
    game.addAction(prepare)
    game.addAction(common.finish(False))
    game.addAction(box)
    game.idle = double_yuhun
    game.start()


if __name__ == "__main__":
    main()
