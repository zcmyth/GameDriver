import sys

from com.dtmilano.android.viewclient import ViewClient

d_id = None
if len(sys.argv) == 2:
    d_id = sys.argv[1]
device, serialno = ViewClient.connectToDeviceOrExit(verbose=False, serialno=d_id)
device.takeSnapshot().save("1.png", 'PNG')
