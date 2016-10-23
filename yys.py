from game import Game
from action import SimpleAction
from devices import create
import time
import utils

def main():
    game = Game(create())
    game.addAction(SimpleAction('skip'))
    game.addAction(SimpleAction('next'))
    game.addAction(SimpleAction('forward'))
    game.addAction(SimpleAction('challenge'))
    game.addAction(SimpleAction('prepare'))
    game.addAction(SimpleAction('talk'))
    game.addAction(SimpleAction('discover'))
    game.addAction(SimpleAction('question'))
    game.addAction(SimpleAction('fight'))
    game.start()


if __name__ == "__main__":
    main()
