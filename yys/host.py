import sys
import common
import time

sys.path.append("..")
from game import Game
from action import SimpleAction, multiClick
from devices import create


def begin(g):
    if g.find("xiaohao"):
        if g.click("begin"):
            time.sleep(2)
            return True
    return False


def invite(g):
    if g.click("double_yuhun"):
        time.sleep(5)
        g.screenshot()
        return g.click("double_yuhun")

    if multiClick(g, ["invite", "xiaohao", "invite1"]):
        return True
    return False


def prepare(g):
    if g.find("can_prepare"):
        return g.click("prepare")
    return False


def fighting(g):
    return g.find('auto') is not None


def main():
    game = Game(create(), debug=True, idle_time=45)
    common.handle_common_interruption(game)
    game.addAction(SimpleAction('ok'))
    game.addAction(begin)
    game.addAction(SimpleAction('fight'))
    game.addAction(prepare)
    # game.addAction(common.select_enemy)
    game.addAction(common.finish(False))
    game.addAction(fighting)
    game.idle = invite
    game.start()


if __name__ == "__main__":
    main()
