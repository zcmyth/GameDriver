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


def host(g):
    if g.find("team"):
        time.sleep(5)
        if not g.find("team"):
            return False
        if not multiClick(g, ["team", "yuhun"]):
            return False
        time.sleep(2)
        g.screenshot()
        if not g.find("level5"):
            return False
        g.drag("level5", "top", 3000)
        time.sleep(2)
        g.screenshot()
        if multiClick(g, ["level10", "create_team", "private", "create"]):
            time.sleep(1)
            g.screenshot()
            return invite(g)
    return False


def invite(g):
    if g.find("double_yuhun"):
        g.click((0.95, 0.5))
        time.sleep(5)
        g.screenshot()
        if g.find("double_yuhun"):
            g.click((0.95, 0.5))
            return True
    if g.find('invite'):
        multiClick(g, ["invite", "xiaohao", "invite1"])
        return True
    return False


def main():
    game = Game(create(), debug=True, idle_time=45)
    game.addAction(SimpleAction('ok'))
    common.handle_common_interruption(game)
    game.addAction(begin)
    game.addAction(host)
    game.idle = invite
    game.start()


if __name__ == "__main__":
    main()
