import sys
import common
import time
from datetime import datetime

sys.path.append("..")
from game import Game
from action import SimpleAction, multiClick
from devices import create


def begin(g):
    if g.find("xiaohao"):
        if g.click("begin"):
            time.sleep(3)
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
        time.sleep(3)
        g.screenshot()
    if g.find("level10") and multiClick(g, ["level10", "create_team", "private", "create"]):
        time.sleep(1)
        g.screenshot()
    return False


def ok_invite(g):
    if g.find("ok"):
        if g.click("default_invite"):
            time.sleep(1)
        return g.click("ok")
    return False


last_invite = None
no_xiaohao = 0


def idle(g):
    global no_xiaohao
    global last_invite
    if g.click("cancel"):
        return True
    if g.find("double_yuhun"):
        g.click((0.95, 0.5))
        time.sleep(5)
        g.screenshot()
        if g.find("double_yuhun"):
            g.click((0.95, 0.5))
            return True

    host(g)

    if g.find('invite'):
        if not multiClick(g, ["invite", "xiaohao"]):
            if no_xiaohao >= 2:
                print "no xiaohao many times, exit"
                exit()
            print "cannot find xiaohao, cancel the window and retry later."
            no_xiaohao = no_xiaohao + 1
            g.screenshot()
            return g.click("cancel")
        time.sleep(1)
        g.screenshot()
        if g.click("invite1"):
            no_xiaohao = 0
            if last_invite and (datetime.now() - last_invite).seconds < 120:
                # the follower might be out of energy, wait
                print "xiaohao is out of energy, sleep and wait for an hour"
                time.sleep(3600)
            last_invite = datetime.now()
        return True
    return True


def main():
    game = Game(create(), debug=True, idle_time=45)
    common.handle_common_interruption(game, False)
    game.addAction(ok_invite)
    game.addAction(begin)
    game.idle = idle
    game.start()


if __name__ == "__main__":
    main()
