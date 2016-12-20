from game import Game
from action import SimpleAction
from devices import create
import time
import utils
import sys


f = '16'
if len(sys.argv) == 2:
    f = sys.argv.pop(1)

fighting = False
failed_count = 0
enemy = (969,220)
center = (640, 360)
left = (275, 594)
right = (884, 594)

def finish(g):
    global failed_count
    global fighting
    finished = g.click('finish')
    if not finished:
        finished = g.click('failed')
        if finished:
            failed_count += 1
            print 'failed %s times' % failed_count
    if finished:
        fighting = False
        for i in xrange(2):
            time.sleep(2)
            g.click(center)
    	return True
    return False

def fight(g):
    global fighting
    g.screenshot()
    if g.click('boss') or g.click('fight'):
        fighting = True
        time.sleep(5)
        g.click(enemy)
    	return True
    return False

def gift(g):
    if g.click('gift'):
        time.sleep(5)
        g.click(center)
    	return True
    return False

def move(g):
    if fighting:
        return True
    print 'searching...'
    for i in xrange(3):
        time.sleep(2)
        g.click(right)
    	if fight(g):
            return True
    for i in xrange(3):
        time.sleep(2)
        g.click(left)
    	if fight(g):
            return True
    return False

def box(g):
    if g.click('box'):
        for i in xrange(2):
            time.sleep(1)
            g.click((150, 360))
        return True
    return False

def main():
    game = Game(create(), idle_time=20, debug=True)
    game.addAction(SimpleAction('busy'))
    game.addAction(SimpleAction('cancel'))
    game.addAction(SimpleAction('accept'))
    game.addAction(gift)
    game.addAction(SimpleAction('discover'))
    game.addAction(SimpleAction(f))
    game.addAction(box)
    game.addAction(fight)
    game.addAction(finish)
    game.idle = move
    game.start()


if __name__ == "__main__":
    main()
