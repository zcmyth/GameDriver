from types import SimpleNamespace

from PIL import Image

from android_access_mcp import device as device_module


class FakeAdbDevice:
    def __init__(self):
        self.info = {'serial': 'phone-1'}
        self.clicked = []
        self.swiped = []

    def window_size(self):
        return 1000, 2000

    def click(self, x, y):
        self.clicked.append((x, y))

    def swipe(self, start_x, start_y, end_x, end_y, duration):
        self.swiped.append((start_x, start_y, end_x, end_y, duration))

    def screenshot(self, _display_id):
        return Image.new('RGB', (100, 200), color='black')


def test_select_preferred_serial_prefers_phone_over_emulator(monkeypatch):
    fake_adb = SimpleNamespace(
        device_list=lambda: [
            SimpleNamespace(serial='emulator-5554', state='device'),
            SimpleNamespace(serial='phone-1', state='device'),
        ]
    )
    monkeypatch.setattr(device_module.adbutils, 'adb', fake_adb)

    serial = device_module.AndroidDevice._select_preferred_serial()

    assert serial == 'phone-1'


def test_click_accepts_normalized_coordinates(monkeypatch):
    fake_device = FakeAdbDevice()
    fake_adb = SimpleNamespace(
        device_list=lambda: [SimpleNamespace(serial='phone-1', state='device')],
        device=lambda serial=None: fake_device,
    )
    monkeypatch.setattr(device_module.adbutils, 'adb', fake_adb)

    device = device_module.AndroidDevice()
    result = device.click(0.5, 0.25)

    assert fake_device.clicked == [(500, 500)]
    assert result.x == 500
    assert result.y == 500
    assert result.width == 1000
    assert result.height == 2000


def test_click_clamps_absolute_coordinates(monkeypatch):
    fake_device = FakeAdbDevice()
    fake_adb = SimpleNamespace(
        device_list=lambda: [SimpleNamespace(serial='phone-1', state='device')],
        device=lambda serial=None: fake_device,
    )
    monkeypatch.setattr(device_module.adbutils, 'adb', fake_adb)

    device = device_module.AndroidDevice()
    result = device.click(1200, -10)

    assert fake_device.clicked == [(999, 0)]
    assert result.x == 999
    assert result.y == 0


def test_swipe_accepts_normalized_coordinates(monkeypatch):
    fake_device = FakeAdbDevice()
    fake_adb = SimpleNamespace(
        device_list=lambda: [SimpleNamespace(serial='phone-1', state='device')],
        device=lambda serial=None: fake_device,
    )
    monkeypatch.setattr(device_module.adbutils, 'adb', fake_adb)

    device = device_module.AndroidDevice()
    result = device.swipe(0.8, 0.75, 0.2, 0.25, duration_ms=400)

    assert fake_device.swiped == [(800, 1500, 200, 500, 0.4)]
    assert result.start_x == 800
    assert result.start_y == 1500
    assert result.end_x == 200
    assert result.end_y == 500
    assert result.duration_ms == 400


def test_swipe_clamps_absolute_coordinates(monkeypatch):
    fake_device = FakeAdbDevice()
    fake_adb = SimpleNamespace(
        device_list=lambda: [SimpleNamespace(serial='phone-1', state='device')],
        device=lambda serial=None: fake_device,
    )
    monkeypatch.setattr(device_module.adbutils, 'adb', fake_adb)

    device = device_module.AndroidDevice()
    result = device.swipe(-10, 2500, 1500, -20)

    assert fake_device.swiped == [(0, 1999, 999, 0, 0.3)]
    assert result.start_x == 0
    assert result.start_y == 1999
    assert result.end_x == 999
    assert result.end_y == 0


def test_swipe_rejects_non_positive_duration(monkeypatch):
    fake_device = FakeAdbDevice()
    fake_adb = SimpleNamespace(
        device_list=lambda: [SimpleNamespace(serial='phone-1', state='device')],
        device=lambda serial=None: fake_device,
    )
    monkeypatch.setattr(device_module.adbutils, 'adb', fake_adb)

    device = device_module.AndroidDevice()

    try:
        device.swipe(0.1, 0.1, 0.9, 0.9, duration_ms=0)
    except ValueError as error:
        assert str(error) == 'duration_ms must be greater than zero'
    else:
        raise AssertionError('Expected ValueError')


def test_current_screen_returns_png_payload(monkeypatch):
    fake_device = FakeAdbDevice()
    fake_adb = SimpleNamespace(
        device_list=lambda: [SimpleNamespace(serial='phone-1', state='device')],
        device=lambda serial=None: fake_device,
    )
    monkeypatch.setattr(device_module.adbutils, 'adb', fake_adb)

    device = device_module.AndroidDevice()
    result = device.current_screen(max_height=100)

    assert result.width == 50
    assert result.height == 100
    assert result.original_width == 100
    assert result.original_height == 200
    assert result.png_base64.startswith('iVBOR')


def test_current_screen_accepts_exact_width_and_height(monkeypatch):
    fake_device = FakeAdbDevice()
    fake_adb = SimpleNamespace(
        device_list=lambda: [SimpleNamespace(serial='phone-1', state='device')],
        device=lambda serial=None: fake_device,
    )
    monkeypatch.setattr(device_module.adbutils, 'adb', fake_adb)

    device = device_module.AndroidDevice()
    result = device.current_screen(width=40, height=80)

    assert result.width == 40
    assert result.height == 80
    assert result.original_width == 100
    assert result.original_height == 200
