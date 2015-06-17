import time
from game import ImageMatchEventHandler, Game, match, loadImage

BBOX = (0, 0, 1440, 900)
IMAGES = [
    'login',
    'login2',
    'ok',
    'task',
    'fight',
    'use_book',
    'submit',
    'gang_task',
    'gang_fight',
    'gang_read'
]

class BuyHandler(ImageMatchEventHandler):
  def __init__(self):
    self.image = loadImage('buy')
    self.need = loadImage('need')
    self.close = loadImage('close')

  def handle(self, game):
    time.sleep(2)
    need_center = match(game.frame, self.need)
    if need_center:
      game.click(need_center)
      time.sleep(2)
    game.click(self.center)
    time.sleep(2)
    close = match(game.frame, self.close)
    if close:
      game.click(close)

class Mhxy(Game):
  def next(self):
    self.tabKey('1')


def main():
  game = Mhxy(BBOX, 5)
  for image in IMAGES:
    game.addEventHandler(ImageMatchEventHandler(image))
  game.addEventHandler(BuyHandler())
  game.start()


if __name__ == "__main__":
  main()
  #game = Mhxy((0,0,100,100))
  #game.showScreenshot()