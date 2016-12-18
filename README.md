# GameDriver
A WebDriver for Game

* Installation for Windows
 * Install any android emulator. For example http://www.xyaz.cn/
  * (Optional) Usually the emulator will include the 'adb' tool, if not install it via Android SDK
  * Add the folder that contains the adb.ext into the environment variables
  * Run the emulator and open cmd, type 'adb devices'. You should be able to see the address of the emulator
 * git@github.com:zcmyth/GameDriver.git
 * Install python
 * Install OpenCV-Python in Windows and Copy cv2.pyd to C:/Python27/lib/site-packages.
 * Now it is good to go

* Usage
 * adb devices
 * adb connect <localhost:port>
 * python ss.py 1.png // This will take a screenshot. Test everything works fine
 * python yys_fuben.py



