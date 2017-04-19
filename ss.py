import sys

from com.dtmilano.android.viewclient import ViewClient
from hosts import HOSTS

d_id = None
if len(sys.argv) == 2:
    d_id = sys.argv[1]
device, serialno = ViewClient.connectToDeviceOrExit(verbose=False, serialno=HOSTS[int(d_id)])
device.takeSnapshot().save("1.png", 'PNG')
