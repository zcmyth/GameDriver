from game import Game
from action import SingleClickAction
import utils


def main():
    game = Game()
    for image in utils.COMMON:
        game.addAction(SingleClickAction(image))
    game.start()


if __name__ == "__main__":
    main()
