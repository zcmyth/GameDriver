import sys
import common

sys.path.append("..")
from game import Game
from action import SimpleAction
from devices import create


def main():
    game = Game(create(), debug=True)
    game.addAction(SimpleAction('accept1'))
    game.addAction(SimpleAction('accept'))
    game.addAction(SimpleAction('prepare'))
    game.addAction(common.finish(False))
    game.addAction(common.select_enemy)
    game.start()


if __name__ == "__main__":
    main()
