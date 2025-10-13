from com.dtmilano.android.viewclient import ViewClient


class AdbDevice(object):
    """Device using adb"""
    def __init__(self, serialno=None):
        self._adb, _id = ViewClient.connectToDeviceOrExit(verbose=False, serialno=serialno)
        print 'connected ' + _id

    @property
    def width(self):
        return self._adb.getProperty('display.width')

    @property
    def height(self):
        return self._adb.getProperty('display.height')

    def screenshot(self):
        return self._adb.takeSnapshot(True)

    def drag(self, start, end, duration):
        self._adb.drag(
            (int(start[0] * self.width), int(start[1] * self.height)),
            (int(end[0] * self.width), int(end[1] * self.height)),
            duration, 3)

    def click(self, x, y):
        """ x and y should be [0, 1] """
        if x < 0 or x > 1 or y < 0 or y > 1:
            print 'Wrong input for click, should be [0, 1] but found (%s, %s)' % (x, y)
            return
        self._adb.touch(int(x * self.width), int(y * self.height))
