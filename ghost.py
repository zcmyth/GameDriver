import time
from game import ImageMatchEventHandler, Game, match, loadImage

BBOX = (0, 0, 1440, 900)
IMAGES = [
    'login',
    'login2',
    'ok',
    'ghost',
    'begin_ghost'
]

def main():
  game = Game(BBOX, 3)
  for image in IMAGES:
    game.addEventHandler(ImageMatchEventHandler(image))
  game.start()


if __name__ == "__main__":
  main()
  #game = Game((0,0,1440,900))
  #game.showScreenshot('begin_ghost', 0.9)
