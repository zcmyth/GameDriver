from game import Game
from action import SingleClickAction

IMAGES = [
    'login',
    'login2',
    'ok',
    'close'
]


def main():
    game = Game()
    for image in IMAGES:
        game.addAction(SingleClickAction(image))
    game.start()


if __name__ == "__main__":
    main()
