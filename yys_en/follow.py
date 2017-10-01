import sys
import common
import time

sys.path.append("..")
from game import Game
from action import SimpleAction, multiClick
from devices import create


def double_yuhun(g):
    if g.find("double_yuhun"):
        g.click((0.95, 0.5))
        time.sleep(5)
        g.screenshot()
        if g.find("double_yuhun"):
            g.click((0.95, 0.5))
            return True
    return False


def ok_accept(g):
    if g.find("default_accept"):
        if multiClick(g, ["default_accept", "no_more_ask", "ok"]):
            return True
    return g.click("accept1")


def main():
    game = Game(create(rate_limit=2, blur=0.005), debug=True)
    game.addAction(ok_accept)
    common.handle_common_interruption(game, False)
    game.idle = double_yuhun
    game.start()


if __name__ == "__main__":
    main()
