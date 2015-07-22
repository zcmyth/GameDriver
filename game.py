import cv2
import numpy
import time
from com.dtmilano.android.viewclient import ViewClient

# the screenshot is taken under the resolution below
DEFAULT_RESOLUTION = 1440.0


class Game(object):

    def __init__(self, width=1440, delay=2, threshold=0.8):
        self._device, _ = ViewClient.connectToDeviceOrExit(verbose=False)
        self._actions = []
        self._delay = delay
        self._scale = width / DEFAULT_RESOLUTION
        self._image_cache = {}

    def _getImage(self, name):
        if name in self._image_cache:
            return self._image_cache[name]
        original = cv2.imread('images/' + name + '.bmp', 0)
        resized = cv2.resize(original, (0, 0), fx=self._scale, fy=self._scale)
        self._image_cache[name] = resized
        return resized

    def screenshot(self):
        # wait the screen to be stable
        time.sleep(self._delay)
        pil_image = self.device.takeSnapshot(True)
        open_cv_image = numpy.array(pil_image)
        self._screen = cv2.cvtColor(open_cv_image, cv2.COLOR_BGR2GRAY)

    def find(self, name):
        w, h = self._getImage(name).shape[::-1]
        res = cv2.matchTemplate(
            self._screen, self._getImage(name), cv2.TM_CCOEFF_NORMED)
        loc = numpy.where(res >= self._threshold)
        for pt in zip(*loc[::-1]):
            return (pt[0] + w / 2, pt[1] + h / 2)

    def click(self, point1, point2=None):
        center = point1
        if point2:
            center = ((point1[0] + point2[0]) / 2, (point1[1] + point2[1]) / 2)
        self._device.touch(center[0], center[1])

    def clickImage(self, name):
        center = self.find(name)
        if center:
            self.click(center)
            return True
        return False

    def drag(self, point1, point2, duration=500):
        self._device.drag(point1, point2, duration)

    def addAction(self, action):
        self._actions.append(action)

    def setStatus(self, status):
        if self._status != status:
            self._status = status
            print status

    def start(self):
        while True:
            self.screenshot()
            for action in self._actions:
                if action(self):
                    break
