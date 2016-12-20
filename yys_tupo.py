from game import Game
from action import SimpleAction
from devices import create
import time
import utils

failed_count = 0
enemy = (937,300)
fighting = False


def finish(g):
    global failed_count
    global fighting
    if g.click('failed'):
        for i in xrange(3):
          time.sleep(1)
          g.click((100,100))
        g.screenshot()
        if g.click('refresh'):
          time.sleep(1)
          g.screenshot()
          if g.click('ok'):
            return True
        exit()
    if g.click('finish'):
        fighting = False
        for i in xrange(3):
          time.sleep(1)
          g.click((100,100))
    	return True
    return False

def fight(g):
    global fighting
    if g.click('challenge'):
        fighting = True
        while not g.click('prepare'):
            g.screenshot()
        while g.click('prepare'):
            g.screenshot()
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
    game.addAction(SimpleAction('busy'))
    game.addAction(SimpleAction('cancel'))
    game.addAction(SimpleAction('accept'))
    game.addAction(fight)
    game.addAction(finish)
    game.addAction(tupo)
    game.start()


if __name__ == "__main__":
    main()
