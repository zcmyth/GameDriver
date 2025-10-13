import sys
import common

sys.path.append("..")
from game import Game
from action import SimpleAction, multiClick
from devices import create


def prepare(g):
    return multiClick(g, ["start_douji", "can_prepare", "prepare", "manual"])


def main():
    game = Game(create(rate_limit=2, blur=0.005), debug=True)
    game.addAction(prepare)
    game.addAction(common.finish(False))
    game.start()


if __name__ == "__main__":
    main()
