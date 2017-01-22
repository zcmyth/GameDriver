import sys
import time
import common
sys.path.append("..")

from game import Game
from action import SimpleAction
from devices import create


enemy1 = (0.75, 0.3)
enemy2 = (0.5, 0.3)
enemy3 = (0.25, 0.3)
ally = (0.757, 0.757)


def latiao(g):
    if g.click('latiao'):
        g.click(ally)
        return True
    return False


def shell(g):
    if g.click('shell'):
        g.click(ally)
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
    g.click(enemy1)
    g.click(enemy2)
    g.click(enemy3)


def main():
    game = Game(create(), idle_time=10, debug=True)
    common.handle_common_interruption(game)
    game.addAction(latiao)
    game.addAction(shell)
    game.addAction(xixue)
    game.idle = attack
    game.start()


if __name__ == "__main__":
    main()
