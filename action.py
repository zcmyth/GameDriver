import time


def multiClick(game, names, retry=5):
    for name in names:
        if not game.click(name, retry=retry):
            return False
        time.sleep(1)
        game.screenshot()
    return True


class SimpleAction(object):
    """Simple action that clicks the given names one by one"""
    def __init__(self, names):
        if not isinstance(names, list):
            self._names = [names]
        else:
            self._names = names

    def __call__(self, game):
        if game.click(self._names[0]):
            return multiClick(game, self._names[1:], 5)
        return False
