import sys
import common

sys.path.append("..")
from game import Game
from action import SimpleAction
from devices import create


def main():
    game = Game(create(), debug=True)
    common.handle_common_interruption(game)
    game.addAction(SimpleAction('challenge'))
    game.addAction(SimpleAction('fight'))
    game.addAction(SimpleAction('prepare'))
    game.addAction(common.select_enemy)
    game.addAction(common.finish(False))
    game.start()


if __name__ == "__main__":
    main()
