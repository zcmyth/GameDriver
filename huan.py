from game import Game
from action import SingleClickAction, MultiClickAction
from utils import rate_limited

IMAGES = [
    'login',
    'login2',
    'ok',
    'fight',
    'submit',
    'task',
    'close'
]

ACTION = (1200, 230)

@rate_limited(0.5)
def gogogo(g):
    g.click(ACTION)


def main():
    game = Game()
    game.addAction(MultiClickAction(['need', 'buy', 'close'], 'buy'))
    for image in IMAGES:
        game.addAction(SingleClickAction(image))
    game.addAction(gogogo)
    game.start()

if __name__ == "__main__":
    main()
    #game = Game()
    #game.screenshot()
    #print game.find('task')
