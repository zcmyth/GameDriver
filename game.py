import cv2
import numpy
import time
import pyscreenshot as ImageGrab
from matplotlib import pyplot as plt
from pymouse import PyMouse
from pykeyboard import PyKeyboard


THRESHOLD = 0.9


def loadImage(name):
  return cv2.imread('images/' + name + '.bmp', 0)


def match(screenshot, query_image, threshold=THRESHOLD):
  w, h = query_image.shape[::-1]
  res = cv2.matchTemplate(screenshot, query_image, cv2.TM_CCOEFF_NORMED)
  loc = numpy.where(res >= threshold)
  for pt in zip(*loc[::-1]):
    return (pt[0] + w / 2, pt[1] + h / 2)


class ImageMatchEventHandler(object):
  def __init__(self, name):
    self.image = loadImage(name)

  def predicate(self, game):
    self.center = match(game.frame, self.image)
    return self.center is not None

  def handle(self, game):
    game.click(self.center)
    

class Game(object):
  def __init__(self, bbox, delay=2):
    self.bbox = bbox
    self.mouse = PyMouse()
    self.keyboard = PyKeyboard()
    self.handlers = []
    self.delay = delay

  def click(self, point):
    self.mouse.click(self.bbox[0] + point[0],
                self.bbox[1] + point[1], 1)

  def tabKey(self, key):
    self.keyboard.tap_key(key)

  def addEventHandler(self, handler):
    self.handlers.append(handler)

  def screenshot(self):
    pil_image = ImageGrab.grab(self.bbox).convert('RGB')
    open_cv_image = numpy.array(pil_image)
    self.frame = cv2.cvtColor(open_cv_image, cv2.COLOR_BGR2GRAY)

  def showScreenshot(self, image=None, threshold=THRESHOLD):
    self.screenshot()
    img_copy = self.frame.copy()
    if image:
      if isinstance(image, str):
        image = loadImage(image)
      w, h = image.shape[::-1]
      center = match(self.frame, image, threshold)
      print center
      if center:
        cv2.rectangle(img_copy,
                      (center[0] - w / 2,center[1] - h / 2),
                      (center[0] + w / 2, center[1] + h / 2),
                      (0,0,255), 2)
    plt.imshow(img_copy,cmap = 'gray')
    plt.show()
    
  def next(self):
    pass

  def start(self):
    while True:
      time.sleep(self.delay)
      self.screenshot()
      handled = False
      for handler in self.handlers:
        if handler.predicate(self):
          handler.handle(self)
          handled = True
      if not handled:
        self.next()
