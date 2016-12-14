from game import Game
from action import SimpleAction
from devices import create
import time
import utils

def multiclick(g):
    g.click((10, 300))
    g.click((10, 300))

def main():
    game = Game(create(), idle_time=3)
    game.addAction(SimpleAction('ok'))
    game.addAction(SimpleAction('cancel'))
    game.addAction(SimpleAction('next'))
    game.addAction(SimpleAction('challenge'))
    game.addAction(SimpleAction('prepare'))
    game.addAction(SimpleAction('fight'))
    game.idle = multiclick
    game.start()


if __name__ == "__main__":
    main()
