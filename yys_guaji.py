from game import Game
from action import SimpleAction
from devices import create
import time
import utils

def main():
    game = Game(create(), idle_time=5)
    game.addAction(SimpleAction('busy'))
    game.addAction(SimpleAction('cancel'))
    game.addAction(SimpleAction('next'))
    game.addAction(SimpleAction('challenge'))
    game.addAction(SimpleAction('prepare'))
    game.addAction(SimpleAction('talk'))
    game.addAction(SimpleAction('skip'))
    game.addAction(SimpleAction('discover'))
    game.addAction(SimpleAction('question'))
    game.addAction(SimpleAction('fight'))
    game.idle = lambda g: g.click((100, 100))
    game.start()


if __name__ == "__main__":
    main()
