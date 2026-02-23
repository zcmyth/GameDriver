import logging
import os
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
    def __init__(self, height=1024, serial: str | None = None):
        self._height = height
        self._adb_device = None
        self._serial = serial or os.getenv('GD_ADB_SERIAL')
        self.logger = logging.getLogger(__name__)
        self._connect()

    @staticmethod
    def _is_emulator_serial(serial: str) -> bool:
        value = str(serial or '').strip().lower()
        return value.startswith('emulator-')

    @classmethod
    def _select_preferred_serial(cls) -> str | None:
        """Prefer physical phone first; fallback to emulator."""

        devices = list(adbutils.adb.device_list())
        if not devices:
            return None

        ready = [d for d in devices if str(getattr(d, 'state', '')).lower() == 'device']
        pool = ready or devices

        def key(item):
            serial = str(getattr(item, 'serial', '')).strip()
            is_emulator = cls._is_emulator_serial(serial)
            return (1 if is_emulator else 0, serial)

        selected = sorted(pool, key=key)[0]
        return str(getattr(selected, 'serial', '')).strip() or None

    def _connect(self):
        serial = self._serial or self._select_preferred_serial()
        if serial:
            self._adb_device = adbutils.adb.device(serial=serial)
            self._serial = serial
        else:
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
