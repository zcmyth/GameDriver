import cv2
import numpy
import utils
import time


class Game(object):

    def __init__(self, device, target_width=1280, threshold=0.8):
        self._device = device
        self._actions = []
        self._image_cache = {}
        self._threshold = threshold
        if target_width == device.width:
            self._scale = 1
        else:
            self._scale = float(device.width) / float(target_width)
        self.idle = None

    def _getImage(self, name):
        if name in self._image_cache:
            return self._image_cache[name]
        original = cv2.imread('images/' + name + '.png', 0)
        resized = cv2.resize(original, (0, 0), fx=self._scale, fy=self._scale)
        self._image_cache[name] = resized
        return self._image_cache[name]

    def screenshot(self):
        pil_image = self._device.screenshot()
        open_cv_image = numpy.array(pil_image)
        self._screen = cv2.cvtColor(open_cv_image, cv2.COLOR_BGR2GRAY)

    def find(self, name):
        w, h = self._getImage(name).shape[::-1]
        res = cv2.matchTemplate(
            self._screen, self._getImage(name), cv2.TM_CCOEFF_NORMED)
        loc = numpy.where(res >= self._threshold)
        for pt in zip(*loc[::-1]):
            return (pt[0] + w / 2, pt[1] + h / 2)

    def click(self, point1, point2=None, retry=0):
        if isinstance(point1, str):
            center = self.find(point1)
            if center:
                print point1
                return self.click(center)
            if retry > 0:
                time.sleep(1)
                self.screenshot()
                return self.click(name, retry=retry - 1)
            return False
        center = point1
        if point2:
            center = ((point1[0] + point2[0]) / 2, (point1[1] + point2[1]) / 2)
        self._device.click(center[0], center[1])
        return True

    def addAction(self, action):
        self._actions.append(action)

    def start(self):
        last_action_time = 0
        while True:
            time.sleep(1)
            self.screenshot()
            for action in self._actions:
                result = action(self)
                if result == None:
                    print 'Action should return result'
                    return
                if result:
                    last_action_time = time.time()
                    break
            if time.time() - last_action_time > 30 and self.idle:
                self.idle(self)
                last_action_time = time.time()
