from utils import rate_limited
from adb_device import AdbDevice
import random


class Builder(object):

    def with_device(self, device_class):
        self._device = device_class
        return self

    def with_limit(self, rate_limit):
        r = rate_limited(rate_limit)
        self._device.click = r(self._device.click)
        return self

    def with_blur(self, pixel_percent):
        click = self._device.click

        def new_click(instance, x, y):
            new_x = random.uniform(x - pixel_percent, x + pixel_percent)
            new_y = random.uniform(y - pixel_percent, y + pixel_percent)
            click(instance, new_x, new_y)
        self._device.click = new_click
        return self

    def build(self, device_id=None):
        return self._device(device_id)


def create(device_id=None, rate_limit=1, blur=0.01):
    return (Builder().with_device(AdbDevice)
            .with_limit(rate_limit)  # two action per second
            .with_blur(blur)   # random change click point
            .build(device_id))
