from game import Game
from action import SingleClickAction, MultiClickAction

IMAGES = [
    'login',
    'login2',
    'ok',
    'task',
    'fight',
    'use_book',
    'submit',
    'gang_task',
    'gang_fight',
    'gang_read',
    'shoufu',
    'close'
]

ACTION = (1400, 230)


def main():
    game = Game(3)
    for image in IMAGES:
        game.addAction(SingleClickAction(image))
    game.addAction(MultiClickAction('buy', 'need', 'close'))
    game.addAction(lambda g: g.click(ACTION))
    game.start()


if __name__ == "__main__":
    main()
