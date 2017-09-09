import sys
import common
import time

sys.path.append("..")
from game import Game
from action import SimpleAction
from devices import create


def challenge(g):
    if not g.find('challenge'):
        return False
    for t in xrange(2):
        if g.click('challenge'):
            for i in xrange(10):
                time.sleep(2)
                g.screenshot()
                if g.find("can_prepare"):
                    return g.click("prepare")
    print 'out of ticket'
    exit()


def main():
    game = Game(create(), debug=True)
    common.handle_common_interruption(game)
    game.addAction(challenge)
    game.start()


if __name__ == "__main__":
    main()
