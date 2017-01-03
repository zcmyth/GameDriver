from com.dtmilano.android.viewclient import ViewClient


class AdbDevice(object):
    """Device using adb"""
    def __init__(self):
        self._adb, _ = ViewClient.connectToDeviceOrExit(verbose=False)

    @property
    def width(self):
        return self._adb.getProperty('display.width')

    @property
    def height(self):
        return self._adb.getProperty('display.height')

    def screenshot(self):
        return self._adb.takeSnapshot(True)

    def click(self, x, y):
        """ x and y should be [0, 1] """
        if x < 0 or x > 1 or y < 0 or y > 1:
            print 'Wrong input for click, should be [0, 1] but found (%s, %s)' % (x, y)
            return
        self._adb.touch(int(x * self.width), int(y * self.height))
