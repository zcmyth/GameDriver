import sys
import time
import common
sys.path.append("..")

from game import Game
from action import SimpleAction
from devices import create


enemy1 = (0.66, 0.31)
enemy2 = (0.5, 0.31)
enemy3 = (0.34, 0.31)
ally1 = (0.25, 0.75)
ally2 = (0.5, 0.6)
ally3 = (0.75, 0.7)


def latiao(g):
    if g.click('latiao'):
        g.click(ally1)
        g.click(ally2)
        g.click(ally3)
        time.sleep(2)
        return True
    return False


def shell(g):
    if g.click('shell'):
        g.click(ally1)
        g.click(ally2)
        g.click(ally3)
        return True
    if g.find('qingming'):
        attack(g)
        return True
    return False


def xixue(g):
    if g.find('xixue'):
        attack(g)
        return True
    return False


def attack(g):
    print 'attack'
    g.click(enemy1)
    g.click(enemy2)
    g.click(enemy3)
    return True


def main():
    game = Game(create(), idle_time=10, debug=True)
    # common.handle_common_interruption(game)
    game.addAction(latiao)
    game.addAction(shell)
    game.addAction(xixue)
    game.idle = attack
    game.start()


if __name__ == "__main__":
    main()
