from game import Game
from action import SimpleAction
from devices import create
import utils


def main():
    game = Game(create())
    for image in ['use'] + utils.COMMON:
        game.addAction(SimpleAction(image))
    game.start()


if __name__ == "__main__":
    main()
