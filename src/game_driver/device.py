import logging
import time
from functools import wraps

import adbutils


def throttle(min_delay: float = 0.5):
   def decorator(func):
       @wraps(func)
       def wrapper(self, *args, **kwargs):
           if not hasattr(self, '_last_action_time'):
               self._last_action_time = 0

           elapsed = time.time() - self._last_action_time
           if elapsed < min_delay:
               time.sleep(min_delay - elapsed)

           result = func(self, *args, **kwargs)
           self._last_action_time = time.time()
           return result
       return wrapper
   return decorator


class Device:
   def __init__(self, height=1024):
       self._height = height
       self._adb_device = None
       self.logger = logging.getLogger(__name__)
       self._connect()

   def _connect(self):
       self._adb_device = adbutils.adb.device()
       info = self._adb_device.info
       self.logger.info(f"Connected to device: {info}")


   @throttle(1)
   def screenshot(self):
       image = self._adb_device.screenshot(0)
       width, height = image.size
       self.width = width
       self.height = height
       if height != self._height:
           ratio = self._height / height
           image = image.resize((int(width * ratio), int(self._height)))
       self.logger.info(f"Screenshot taken: {width}x{height} -> {image.width}x{image.height}")
       return image


   @throttle(1)
   def click(self, x, y):
       w, h = self._adb_device.window_size()
       actual_x = int(x * w)
       actual_y = int(y * h)
       self.logger.info(f"Clicking at relative ({x:.3f}, {y:.3f}) -> pixel ({actual_x}, {actual_y})")
       self._adb_device.click(actual_x, actual_y)


