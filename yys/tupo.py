import sys
import time
import common
sys.path.append("..")

from game import Game
from action import SimpleAction
from devices import create


any_point = (0.1, 0.1)


def failed(g):
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
    return False


def tupo(g):
    if g.click('tupo2') or g.click('tupo1') or g.click('tupo'):
        return True
    return False


def outOfTicket(g):
    if g.find('zero_tupo'):
        print 'out of ticket'
        exit()
    return False


def main():
    game = Game(create(), idle_time=10, debug=True)
    game.addAction(failed)
    common.handle_common_interruption(game)
    game.addAction(outOfTicket)
    game.addAction(SimpleAction('tupo_attack'))
    game.addAction(tupo)
    game.start()


if __name__ == "__main__":
    main()
