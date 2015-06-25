import time
from game import ImageMatchEventHandler, Game, match, loadImage

IMAGES = [
    'login',
    'login2',
    'ok',
    'ghost',
    'begin_ghost'
]


class Mhxy(Game):
  def next(self):
    pass


def main():
  game = Mhxy(3)
  for image in IMAGES:
    game.addEventHandler(ImageMatchEventHandler(image))
  game.start()


if __name__ == "__main__":
  main()
  #game = Game()
  #game.showScreenshot('begin_ghost', 0.8)
