import cv2
import numpy
from matplotlib import pyplot as plt
import pyscreenshot as ImageGrab
from pymouse import PyMouse

THRESHOLD = 0.9
MOUSE = PyMouse()
BBOX = (2000, 0, 3000, 500)

def screenshot(bbox):
  pil_image = ImageGrab.grab(bbox).convert('RGB')
  open_cv_image = numpy.array(pil_image)
  return cv2.cvtColor(open_cv_image, cv2.COLOR_BGR2GRAY)


def match(screenshot, query_name, threshold=THRESHOLD):
  query_image = cv2.imread(query_name + '.png', 0)
  w, h = query_image.shape[::-1]
  res = cv2.matchTemplate(screenshot, query_image, cv2.TM_CCOEFF_NORMED)
  loc = numpy.where(res >= threshold)
  for pt in zip(*loc[::-1]):
    return (pt[0] + w / 2, pt[1] + h / 2)


def showMatch(screenshot, point):
  img_copy = screenshot.copy()
  cv2.rectangle(img_copy, (point[0] - 5, point[1] - 5), (point[0] + 5, point[1] + 5), (0,0,255), 2)
  plt.imshow(img_copy,cmap = 'gray')
  plt.show()


def click(point):
  MOUSE.click(BBOX[0] + point[0], BBOX[1] + point[1], 1)


def main():
  frame = screenshot(BBOX)
  point = match(frame, 'profile')
  if point:
    click(point)
    showMatch(frame, point)

if __name__ == "__main__":
  main()
