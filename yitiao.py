from game import Game
from action import SingleClickAction
import time
import utils

@utils.rate_limited(0.1, block=False)
def next(g):
    if g.clickImage('mowang') or g.clickImage('digua'):
        time.sleep(2)
        return True

def task(g):
    point = g.find('choose')
    if point:
        g.click((point[0], point[1] + 80))
        return True

def main():
    game = Game()
    game.addAction(next)
    game.addAction(task)
    for image in ['continue'] + utils.COMMON:
        game.addAction(SingleClickAction(image))
    game.start()

if __name__ == "__main__":
    main()
