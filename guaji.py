from game import Game
from action import SimpleAction
from devices import create
import time
import utils


def baby(g):
  if g.find('baby'):
    print 'Baby'
    print '\a'


def defence_for_target(g):
  if g.find('guijiang'):
    print 'Find it!!!!!!!!'
    print '\a'
    g.click('cancel')
    time.sleep(5)
    g.click('defence')
    time.sleep(5)
    g.click('defence')
    time.sleep(5)


def main():
    game = Game(create())
    for image in utils.COMMON:
        game.addAction(SimpleAction(image))
    game.addAction(defence_for_target)
    game.start()


if __name__ == "__main__":
    print '\a'
    main()
