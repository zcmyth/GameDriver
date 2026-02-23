from types import SimpleNamespace

from game_driver import device as device_module


def test_select_preferred_serial_prefers_phone_over_emulator(monkeypatch):
    fake_adb = SimpleNamespace(
        device_list=lambda: [
            SimpleNamespace(serial='emulator-5554', state='device'),
            SimpleNamespace(serial='29131FDH200FJQ', state='device'),
        ]
    )
    monkeypatch.setattr(device_module.adbutils, 'adb', fake_adb)

    serial = device_module.Device._select_preferred_serial()

    assert serial == '29131FDH200FJQ'


def test_select_preferred_serial_falls_back_to_emulator(monkeypatch):
    fake_adb = SimpleNamespace(
        device_list=lambda: [
            SimpleNamespace(serial='emulator-5554', state='device'),
        ]
    )
    monkeypatch.setattr(device_module.adbutils, 'adb', fake_adb)

    serial = device_module.Device._select_preferred_serial()

    assert serial == 'emulator-5554'


def test_device_connect_uses_explicit_serial_env(monkeypatch):
    captured = {'serial': None}

    def fake_device(*, serial=None):
        captured['serial'] = serial
        return SimpleNamespace(info={'serial': serial})

    fake_adb = SimpleNamespace(
        device_list=lambda: [SimpleNamespace(serial='emulator-5554', state='device')],
        device=fake_device,
    )
    monkeypatch.setattr(device_module.adbutils, 'adb', fake_adb)
    monkeypatch.setenv('GD_ADB_SERIAL', 'emulator-5554')

    device_module.Device(height=100)

    assert captured['serial'] == 'emulator-5554'
