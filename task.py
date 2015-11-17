from game import Game
from action import SimpleAction, multiClick
import time
import utils
from devices import create

ACTION = (1200, 230)

def task(g):
    point = g.find('choose')
    if point:
        return g.click((point[0], point[1] + 80))
    return False


def buy(g):
    point = g.find('buy')
    if point:
        time.sleep(1)
        g.screenshot()
        need = g.find('need')
        if not need:
            return multiClick(g, [point, 'close'])
        else:
            return multiClick(g, ['need', 'buy', 'close'])
    return False


def main():
    game = Game(create(), idle_time=5)
    game.addAction(task)
    game.addAction(buy)
    for image in ['use'] + utils.COMMON:
        game.addAction(SimpleAction(image))
    game.idle = lambda g : g.click(ACTION)
    game.start()

if __name__ == "__main__":
    main()
