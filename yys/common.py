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


def prepare(g):
    if g.find("can_prepare"):
        return g.click("prepare")
    return False


def finish(g):
    if g.find("finish1"):
        g.screenshot()
        result = g.click("finish1")
        time.sleep(1)
        return result
    if g.find("finish2"):
        time.sleep(2)
        g.screenshot()
        result = g.click("finish2")
        time.sleep(1)
        return result
    return False


def login(g):
    if g.find("yys"):
        if multiClick(g, ["yys", "cg", "close", "enter_game"], 10, 5):
            for i in xrange(5):
                time.sleep(5)
                g.screenshot()
                if not g.click("enter_game"):
                    break
            return multiClick(g, ["shenle", "task"], 10, 5)
    return False


def handle_common_interruption(g):
    g.addAction(SimpleAction('reject'))
    g.addAction(SimpleAction('busy'))
    g.addAction(finish)
    # g.addAction(SimpleAction('finish2'))
    g.addAction(prepare)
    # g.addAction(SimpleAction('cancel'))
    g.addAction(exit_if_no_energy)
    g.addAction(login)
