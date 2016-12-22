# GameDriver
A WebDriver for Game

* Installation for Windows
  * Install any android emulator. For example http://www.xyaz.cn/
    * (Optional) Usually the emulator will include the `adb` tool, if not, install it via Android SDK.
    * Add the folder that contains the adb.exe into the environment variables. For xyaz, add `C:\Program Files\Microvirt\MEmu` to the `PATH` variable.
    * Run the emulator and open cmd, type `adb devices`. You should be able to see the address of the emulator.
  * `git clone git@github.com:zcmyth/GameDriver.git`
  * Install python and make sure the `C:\Python27` is in the `PATH` variable as well.
  * Install python dependency `pip install -r requirements.txt`
  * Install OpenCV-Python in Windows and copy `cv2.pyd` to `C:/Python27/lib/site-packages`
    * `echo 'import cv2' | python` # Check no error messages.

* Usage
  * `adb devices` # to find the emulator port
  * `adb connect <localhost:port>`
  * `python ss.py 1.png` # This will take a screenshot. Test everything works fine
  * `cd yys`
  * `python fuben.py`
