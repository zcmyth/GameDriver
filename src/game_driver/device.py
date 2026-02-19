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
        self.logger.info(f'Connected to device: {info}')

    @throttle(1)
    def screenshot(self):
        try:
            image = self._adb_device.screenshot(0)
        except Exception:
            self.logger.exception(
                'Screenshot failed, reconnecting ADB and retrying once'
            )
            self._connect()
            image = self._adb_device.screenshot(0)

        width, height = image.size
        self.width = width
        self.height = height
        if height != self._height:
            ratio = self._height / height
            image = image.resize((int(width * ratio), int(self._height)))
        return image

    @throttle(1)
    def click(self, x, y):
        # Accept either normalized coords [0, 1] or absolute pixels.
        w, h = self._adb_device.window_size()
        actual_x = int(x * w) if 0 <= x <= 1 else int(x)
        actual_y = int(y * h) if 0 <= y <= 1 else int(y)

        # Keep clicks on-screen.
        actual_x = max(0, min(actual_x, w - 1))
        actual_y = max(0, min(actual_y, h - 1))

        try:
            self._adb_device.click(actual_x, actual_y)
        except Exception:
            self.logger.exception('Click failed, reconnecting ADB and retrying once')
            self._connect()
            self._adb_device.click(actual_x, actual_y)
