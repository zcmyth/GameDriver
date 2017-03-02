import sys
import time
import common
sys.path.append("..")

from game import Game
from action import SimpleAction
from devices import create


any_point = (0.1, 0.1)


exit_on_fail = True
if len(sys.argv) == 2:
    exit_on_fail = False


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
        if exit_on_fail:
            exit()
    if g.click('finish1') or g.click('continue'):
        time.sleep(1)
        g.click(any_point)
        time.sleep(1)
        g.screenshot()
        return g.click('finish2')
    return False


def tupo(g):
    if g.click('tupo2') or g.click('tupo1') or g.click('tupo'):
        return True
    return False


def main():
    game = Game(create(), idle_time=10, debug=True)
    common.handle_common_interruption(game)
    game.addAction(SimpleAction('attack'))
    game.addAction(SimpleAction('prepare'))
    game.addAction(tupo)
    game.addAction(common.select_enemy)
    game.addAction(finish)
    game.idle = lambda g: g.click(any_point)
    game.start()


if __name__ == "__main__":
    main()
