from game import Game
from utils import COMMON
from action import SimpleAction
from devices import create


def main():
    game = Game(create())
    game.addAction(SimpleAction(['task', 'ghost', 'ghost']))
    for image in COMMON:
        game.addAction(SimpleAction(image))
    game.idle = lambda g: g.click('ghost')
    game.start()


if __name__ == "__main__":
    main()
