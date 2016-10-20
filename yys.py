from game import Game
from action import SimpleAction
from devices import create
import time
import utils

def main():
    game = Game(create())
    game.addAction(SimpleAction('next'))
    game.addAction(SimpleAction('challenge'))
    game.addAction(SimpleAction('prepare'))
    game.start()


if __name__ == "__main__":
    main()
