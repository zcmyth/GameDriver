from game import Game
from utils import rate_limited
from action import SingleClickAction, MultiClickAction
import time

IMAGES = [
  'main',
  'use',
  'continue'
]

ACTION = (1200, 330)

def task(g):
    point = g.find('bang_help')
    if point:
        g.click((point[0], point[1] - 70))
        return
    point = g.find('video')
    if point:
        g.click((point[0], point[1] - 70))

@rate_limited(0.2, block=False)
def clickNext(g):
    g.click(ACTION)

def main():
    game = Game()
    game.addAction(task)
    for image in IMAGES:
        game.addAction(SingleClickAction(image))
    game.addAction(clickNext)
    game.start()

if __name__ == "__main__":
    main()
    #game = Game()
    #game.screenshot()
    #print game.find('task')
