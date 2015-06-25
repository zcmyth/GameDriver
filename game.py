import cv2
import numpy
import time
from matplotlib import pyplot as plt
from com.dtmilano.android.viewclient import ViewClient

DEFAULT_RESOLUTION = 1440.0
CURRENT_RESOLUTION = 1280
ACTION = (1200, 200)
SCALE = CURRENT_RESOLUTION / DEFAULT_RESOLUTION
THRESHOLD = 0.8


def loadImage(name):
  original = cv2.imread('images/' + name + '.bmp', 0)
  return cv2.resize(original, (0,0), fx=SCALE, fy=SCALE) 


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
  def __init__(self, delay=2):
    self.device, _ = ViewClient.connectToDeviceOrExit(verbose=False)
    self.handlers = []
    self.delay = delay

  def click(self, point1, point2=None):
    center = point1
    if point2:
      center = ((point1[0] + point2[0])/2, (point1[1] + point2[1])/2)
    self.device.touch(center[0], center[1])

  def addEventHandler(self, handler):
    self.handlers.append(handler)

  def screenshot(self):
    pil_image = self.device.takeSnapshot(True)
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
      if center:
        cv2.rectangle(img_copy,
                      (center[0] - w / 2,center[1] - h / 2),
                      (center[0] + w / 2, center[1] + h / 2),
                      (0,0,255), 2)
    plt.imshow(img_copy,cmap = 'gray')
    plt.show()
    
  def next(self):
    self.click(ACTION)

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
