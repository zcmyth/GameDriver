from game import Game
from action import SingleClickAction, MultiClickAction

IMAGES = [
    'login',
    'login2',
    'ok',
    'fight',
    'use',
    'submit',
    'task',
    'gang_task',
    'gang_fight',
    'shoufu',
    'close'
]

ACTION = (1100, 230)


def main():
    game = Game()
    game.addAction(MultiClickAction(['need', 'buy', 'close'], 'buy'))
    for image in IMAGES:
        game.addAction(SingleClickAction(image))
    game.addAction(lambda g: g.click(ACTION))
    game.start()

if __name__ == "__main__":
    main()
    # game = Game()
    # game.screenshot()
    # print game.find('buy')
