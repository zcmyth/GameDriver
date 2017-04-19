import sys
import time

sys.path.append("..")
from action import SimpleAction


enemy = (0.728, 0.27)
center = (0.7, 0.7)


def finish(exit):
    def finish_fn(g):
        if g.click('continue'):
            return True
        if g.find('finish3'):
            g.click(center)
            return True
        finished = g.click('finish1')
        if not finished and exit:
            finished = g.click('failed')
            if finished:
                exit()
        if finished:
            time.sleep(1)
            g.click(center)
            time.sleep(1)
            g.screenshot()
            g.click('finish2')
            time.sleep(1)
            g.click(center)
            return True
        return False
    return finish_fn


def select_enemy(g):
    if g.find('auto') or g.find('x2'):
        g.click(enemy)
        return True
    return False


def exit_if_no_energy(g):
    if g.find('energy'):
        exit()
    return False


def handle_common_interruption(g):
    g.addAction(SimpleAction('accept'))
    g.addAction(SimpleAction('busy'))
    # g.addAction(SimpleAction('cancel'))
    g.addAction(exit_if_no_energy)
