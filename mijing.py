from game import Game
from action import SingleClickAction

IMAGES = [
    'login',
    'login2',
    'ok',
    'fight',
    'mijing',
    'close'
]


def main():
    game = Game(3)
    for image in IMAGES:
        game.addAction(SingleClickAction(image))
    game.start()


if __name__ == "__main__":
    main()
