class SingleClickAction(object):

    def __init__(self, name, status=None):
        self._name = name
        self._status = status if status else name

    def __call__(self, game):
        if game.clickImage(self._name):
            game.setStatus(self._name)
            return True
        return False


class MultiClickAction(object):

    def __init__(self, names, status):
        self._names = names
        self._status = status

    def __call__(self, game):
        for name in self._names:
            game.screenshot()
            if not game.clickImage(name):
                return False
        game.setStatus(self._status)
        return True
