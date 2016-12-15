from com.dtmilano.android.viewclient import ViewClient


class AdbDevice(object):
    """Device using adb"""
    def __init__(self):
        self._adb, _ = ViewClient.connectToDeviceOrExit(verbose=False)

    @property
    def width(self):
        return self._adb.getProperty('display.width')

    def screenshot(self):
        return self._adb.takeSnapshot(True)

    def click(self, x, y):
        #print 'click %s %s' % (x, y)
        self._adb.touch(x, y)
