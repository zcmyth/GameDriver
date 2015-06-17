import time
from game import ImageMatchEventHandler, Game, match, loadImage

BBOX = (0, 0, 1440, 900)
IMAGES = [
    'login',
    'login2',
    'ok'
]

class GhostHandler(ImageMatchEventHandler):
  def __init__(self):
    self.image = loadImage('ghost')
    self.begin = loadImage('begin_ghost')

  def handle(self, game):
    game.click(self.center)
    time.sleep(2)
    begin_center = match(game.frame, self.begin)
    if begin_center:
      game.click(begin_center)


def main():
  game = Game(BBOX, 5)
  for image in IMAGES:
    game.addEventHandler(ImageMatchEventHandler(image))
  game.addEventHandler(GhostHandler())
  game.start()


if __name__ == "__main__":
  main()
