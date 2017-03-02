import sys
import common

sys.path.append("..")
from game import Game
from action import SimpleAction
from devices import create


def begin(g):
    if g.find("xiaohao"):
        return g.click("begin")
    return False


def main():
    if len(sys.argv) == 2:
        game = Game(create(sys.argv[1]), debug=True)
    else:
        game = Game(create(), debug=True)
    game.addAction(SimpleAction('ok'))
    game.addAction(begin)
    game.addAction(SimpleAction('fight'))
    game.addAction(SimpleAction('prepare'))
    game.addAction(common.select_enemy)
    game.addAction(common.finish(False))
    common.handle_common_interruption(game)
    game.start()


if __name__ == "__main__":
    main()
