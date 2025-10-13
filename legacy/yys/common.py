import sys
import time

sys.path.append("..")
from action import SimpleAction, multiClick


def exit_if_no_energy(g):
    if g.find('energy'):
        time.sleep(5)
        g.screenshot()
        if g.find('energy'):
            print 'out of energy'
            exit()
    return False


def wait_if_no_energy(g):
    if g.find('energy'):
        time.sleep(5)
        g.screenshot()
        if g.find('energy'):
            print 'out of energy, wait for an hour'
            g.click("close")
            time.sleep(3600)
            return True
    return False


def prepare(g):
    if g.find("can_prepare"):
        return g.click("prepare")
    return False


def finish(g):
    if g.find("finish1"):
        if g.click("finish1"):
            time.sleep(4)
            g.screenshot()
    if g.find("finish2"):
        if g.click("finish2"):
            time.sleep(2)
            return True
    return False


def login(g):
    if g.find("yys"):
        if multiClick(g, ["yys", "cg", "close", "enter_game1"], 10, 5):
            while True:
                time.sleep(5)
                g.screenshot()
                if not g.click("enter_game1"):
                    break
            multiClick(g, ["shenle", "close"], 5, 3)
            while True:
                time.sleep(5)
                g.screenshot()
                if not g.click("close"):
                    break
            return g.click("task", 3)
    return False


def handle_common_interruption(g, exit=True):
    g.addAction(finish)
    g.addAction(prepare)
    g.addAction(SimpleAction('reject'))
    g.addAction(SimpleAction('busy'))
    if exit:
        g.addAction(exit_if_no_energy)
    else:
        g.addAction(wait_if_no_energy)
    g.addAction(login)
