from __future__ import annotations

import base64
import io
import logging
import os
import re
import time
from dataclasses import dataclass
from functools import wraps
from typing import Any

import adbutils


def throttle(min_delay: float = 0.5):
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            elapsed = time.time() - self._last_action_time
            if elapsed < min_delay:
                time.sleep(min_delay - elapsed)

            result = func(self, *args, **kwargs)
            self._last_action_time = time.time()
            return result

        return wrapper

    return decorator


@dataclass(frozen=True)
class ClickResult:
    requested_x: float
    requested_y: float
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class SwipeResult:
    requested_start_x: float
    requested_start_y: float
    requested_end_x: float
    requested_end_y: float
    start_x: int
    start_y: int
    end_x: int
    end_y: int
    width: int
    height: int
    duration_ms: int


@dataclass(frozen=True)
class KeyEventResult:
    key: str
    output: str


@dataclass(frozen=True)
class ScreenResult:
    width: int
    height: int
    png_base64: str
    original_width: int
    original_height: int


class AndroidDevice:
    def __init__(self, serial: str | None = None):
        self._adb_device: Any | None = None
        self._serial = (
            serial
            or os.getenv('ANDROID_ACCESS_ADB_SERIAL')
            or os.getenv('GD_ADB_SERIAL')
        )
        self._last_action_time = 0.0
        self.logger = logging.getLogger(__name__)
        self._connect()

    @staticmethod
    def _is_emulator_serial(serial: str) -> bool:
        value = str(serial or '').strip().lower()
        return value.startswith('emulator-')

    @classmethod
    def _select_preferred_serial(cls) -> str | None:
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

    def _connect(self) -> None:
        serial = self._serial or self._select_preferred_serial()
        if serial:
            self._adb_device = adbutils.adb.device(serial=serial)
            self._serial = serial
        else:
            self._adb_device = adbutils.adb.device()

        self.logger.info('Connected to Android device: %s', self._adb_device.info)

    @property
    def serial(self) -> str | None:
        return self._serial

    def window_size(self) -> tuple[int, int]:
        width, height = self._adb_device.window_size()
        return int(width), int(height)

    @staticmethod
    def _screen_coordinate(value: float, axis_length: int) -> int:
        requested = float(value)
        actual = int(requested * axis_length) if 0 <= requested <= 1 else int(requested)
        return max(0, min(actual, axis_length - 1))

    @throttle(0.25)
    def current_screen(
        self,
        max_height: int | None = None,
        width: int | None = None,
        height: int | None = None,
    ) -> ScreenResult:
        try:
            image = self._adb_device.screenshot(0)
        except Exception:
            self.logger.exception(
                'Screenshot failed, reconnecting ADB and retrying once'
            )
            self._connect()
            image = self._adb_device.screenshot(0)

        original_width, original_height = image.size
        if width is not None:
            width = int(width)
            if width <= 0:
                raise ValueError('width must be greater than zero')
        if height is not None:
            height = int(height)
            if height <= 0:
                raise ValueError('height must be greater than zero')

        if width is not None and height is not None:
            image = image.resize((width, height))
        elif width is not None:
            ratio = width / original_width
            image = image.resize((width, max(1, int(original_height * ratio))))
        elif height is not None:
            ratio = height / original_height
            image = image.resize((max(1, int(original_width * ratio)), height))
        elif max_height is not None:
            max_height = int(max_height)
            if max_height <= 0:
                raise ValueError('max_height must be greater than zero')
            if original_height > max_height:
                ratio = max_height / original_height
                image = image.resize((max(1, int(original_width * ratio)), max_height))

        output = io.BytesIO()
        image.save(output, format='PNG')
        width, height = image.size
        return ScreenResult(
            width=width,
            height=height,
            original_width=original_width,
            original_height=original_height,
            png_base64=base64.b64encode(output.getvalue()).decode('ascii'),
        )

    @throttle(0.1)
    def click(self, x: float, y: float) -> ClickResult:
        requested_x = float(x)
        requested_y = float(y)
        width, height = self.window_size()
        actual_x = self._screen_coordinate(requested_x, width)
        actual_y = self._screen_coordinate(requested_y, height)

        try:
            self._adb_device.click(actual_x, actual_y)
        except Exception:
            self.logger.exception('Click failed, reconnecting ADB and retrying once')
            self._connect()
            self._adb_device.click(actual_x, actual_y)

        return ClickResult(
            requested_x=requested_x,
            requested_y=requested_y,
            x=actual_x,
            y=actual_y,
            width=width,
            height=height,
        )

    @throttle(0.1)
    def swipe(
        self,
        start_x: float,
        start_y: float,
        end_x: float,
        end_y: float,
        duration_ms: int = 300,
    ) -> SwipeResult:
        requested_start_x = float(start_x)
        requested_start_y = float(start_y)
        requested_end_x = float(end_x)
        requested_end_y = float(end_y)
        duration_ms = int(duration_ms)
        if duration_ms <= 0:
            raise ValueError('duration_ms must be greater than zero')

        width, height = self.window_size()
        actual_start_x = self._screen_coordinate(requested_start_x, width)
        actual_start_y = self._screen_coordinate(requested_start_y, height)
        actual_end_x = self._screen_coordinate(requested_end_x, width)
        actual_end_y = self._screen_coordinate(requested_end_y, height)

        try:
            self._adb_device.swipe(
                actual_start_x,
                actual_start_y,
                actual_end_x,
                actual_end_y,
                duration_ms / 1000,
            )
        except Exception:
            self.logger.exception('Swipe failed, reconnecting ADB and retrying once')
            self._connect()
            self._adb_device.swipe(
                actual_start_x,
                actual_start_y,
                actual_end_x,
                actual_end_y,
                duration_ms / 1000,
            )

        return SwipeResult(
            requested_start_x=requested_start_x,
            requested_start_y=requested_start_y,
            requested_end_x=requested_end_x,
            requested_end_y=requested_end_y,
            start_x=actual_start_x,
            start_y=actual_start_y,
            end_x=actual_end_x,
            end_y=actual_end_y,
            width=width,
            height=height,
            duration_ms=duration_ms,
        )

    @throttle(0.1)
    def keyevent(self, key: str | int) -> KeyEventResult:
        key_value = str(key).strip().upper()
        if not re.fullmatch(r'[A-Z0-9_]+', key_value):
            raise ValueError('key must contain only letters, numbers, or underscores')

        try:
            output = self._adb_device.shell(['input', 'keyevent', key_value])
        except Exception:
            self.logger.exception('Keyevent failed, reconnecting ADB and retrying once')
            self._connect()
            output = self._adb_device.shell(['input', 'keyevent', key_value])

        return KeyEventResult(key=key_value, output=str(output or ''))

    def back(self) -> KeyEventResult:
        return self.keyevent('BACK')
