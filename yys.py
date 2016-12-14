from game import Game
from action import SimpleAction
from devices import create
import time
import utils

fighting = False
failed_count = 0
enemy = (937,300)

def finish(g):
    global fighting
    global failed_count
    finished = g.click('finish')
    if not finished:
        finished = g.click('failed')
        if finished:
            failed_count += 1
            print 'failed %s times' % failed_count
    if finished:
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
            time.sleep(1)
            g.click(enemy)
    	return True
    return False

def selectEnemy(g):
    if fighting :
        for i in xrange(3):
          time.sleep(1)
          g.click(enemy)
        return True
    return False 

def main():
    game = Game(create(), idle_time=5)
    game.addAction(SimpleAction('busy'))
    game.addAction(SimpleAction('cancel'))
    game.addAction(fight)
    game.addAction(finish)
    game.addAction(selectEnemy)
    game.start()


if __name__ == "__main__":
    main()