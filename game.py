import cv2
import numpy
import utils
from com.dtmilano.android.viewclient import ViewClient


class Game(object):

    def __init__(self, threshold=0.8):
        self._device, _ = ViewClient.connectToDeviceOrExit(verbose=False)
        self._actions = []
        self._image_cache = {}
        self._threshold = threshold
        self._status = None

    def _getImage(self, name):
        if name in self._image_cache:
            return self._image_cache[name]
        original = cv2.imread('images/' + name + '.png', 0)
        #resized = cv2.resize(original, (0, 0), fx=self._scale, fy=self._scale)
        self._image_cache[name] = original
        return self._image_cache[name]

    @utils.rate_limited(0.4)
    def screenshot(self):
        # wait the screen to be stable
        pil_image = self._device.takeSnapshot(True)
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
            print 'clicked ' + name
            return True
        return False

    def drag(self, point1, point2, duration=500):
        self._device.drag(point1, point2, duration)

    def addAction(self, action):
        self._actions.append(action)

    def setStatus(self, status):
        #if self._status != status:
        #    self._status = status
        #print status
        pass

    def start(self):
        while True:
            self.screenshot()
            for action in self._actions:
                if action(self):
                    break
