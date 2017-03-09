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
    if len(sys.argv) == 2:
        game = Game(create(sys.argv[1], rate_limit=2, blur=0.005), debug=True)
    else:
        game = Game(create('127.0.0.1:21533', rate_limit=2, blur=0.005), debug=True)
    game.addAction(SimpleAction('accept1'))
    common.handle_common_interruption(game)
    game.addAction(prepare)
    game.addAction(common.finish(False))
    game.start()


if __name__ == "__main__":
    main()
