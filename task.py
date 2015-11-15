from game import Game
from action import SimpleAction
import time
import utils
from devices import create

ACTION = (1200, 230)

def task(g):
    point = g.find('choose')
    if point:
        return g.click((point[0], point[1] + 80))
    return False

def next(g):
    g.click(ACTION)
    time.sleep(10)
    return True

def main():
    game = Game(create())
    game.addAction(task)
    game.addAction(SimpleAction(['need', 'buy', 'close']))
    for image in ['use'] + utils.COMMON:
        game.addAction(SimpleAction(image))
    game.addAction(next)
    game.start()

if __name__ == "__main__":
    main()
