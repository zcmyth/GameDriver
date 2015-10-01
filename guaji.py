from game import Game
from action import SingleClickAction
import time

IMAGES = [
    'login',
    'login2',
    'ok',
    'close'
]

def baby(g):
  if g.find('baby'):
    print 'Baby'
    print '\a'


def defence_for_target(g):
  if g.find('guijiang'):
    print 'Find it!!!!!!!!'
    print '\a'
    g.clickImage('cancel')
    time.sleep(5)
    g.clickImage('defence')
    time.sleep(5)
    g.clickImage('defence')
    time.sleep(5)


def main():
    game = Game()
    for image in IMAGES:
        game.addAction(SingleClickAction(image))
    game.addAction(defence_for_target)
    game.start()


if __name__ == "__main__":
    print '\a'
    main()
