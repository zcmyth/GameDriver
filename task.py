from game import Game
from action import SingleClickAction, MultiClickAction
import time
import utils

ACTION = (1200, 230)

def task(g):
    point = g.find('choose')
    if point:
        g.click((point[0], point[1] + 80))
        return True

def main():
    game = Game()
    game.addAction(task)
    game.addAction(MultiClickAction(['need', 'buy', 'close'], 'buy'))
    for image in ['use'] + utils.COMMON:
        game.addAction(SingleClickAction(image))
    game.addAction(lambda g: g.click(ACTION))
    game.start()

if __name__ == "__main__":
    main()
    #game = Game()
    #game.screenshot()
    #print game.find('task')
