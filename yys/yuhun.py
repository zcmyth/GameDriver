import sys
import common

sys.path.append("..")
from game import Game
from action import SimpleAction
from devices import create


def prepare(g):
    if g.find("can_prepare"):
        return g.click("prepare")
    return False


def main():
    game = Game(create(), debug=True)
    common.handle_common_interruption(game)
    game.addAction(SimpleAction('challenge'))
    game.addAction(SimpleAction('fight'))
    game.addAction(prepare)
    # game.addAction(common.select_enemy)
    game.addAction(common.finish(False))
    game.start()


if __name__ == "__main__":
    main()
