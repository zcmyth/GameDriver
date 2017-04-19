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


def challenge(g):
    if g.click('challenge'):
        for i in xrange(10):
            time.sleep(2)
            g.screenshot()
            if g.find("can_prepare"):
                return g.click("prepare")
        print 'out of ticket'
        exit()
    return False


def main():
    game = Game(create(), debug=True)
    common.handle_common_interruption(game)
    game.addAction(challenge)
    game.addAction(prepare)
    # game.addAction(common.select_enemy)
    game.addAction(common.finish(False))
    game.start()


if __name__ == "__main__":
    main()
