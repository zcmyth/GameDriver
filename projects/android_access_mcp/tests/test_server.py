import json

from PIL import Image

from android_access_mcp.device import ClickResult, ScreenResult, SwipeResult
from android_access_mcp.server import AndroidAccessMcpServer


class FakeDevice:
    serial = 'phone-1'

    def __init__(self):
        self.clicks = []
        self.swipes = []

    def current_screen(self, max_height=None, width=None, height=None):
        image = Image.new('RGB', (1, 1), color='black')
        assert image.size == (1, 1)
        assert max_height == 100
        assert width == 20
        assert height == 40
        return ScreenResult(
            width=20,
            height=40,
            original_width=1,
            original_height=1,
            png_base64='fakepng',
        )

    def click(self, x, y):
        self.clicks.append((x, y))
        return ClickResult(
            requested_x=float(x),
            requested_y=float(y),
            x=10,
            y=20,
            width=100,
            height=200,
        )

    def swipe(self, start_x, start_y, end_x, end_y, duration_ms=300):
        self.swipes.append((start_x, start_y, end_x, end_y, duration_ms))
        return SwipeResult(
            requested_start_x=float(start_x),
            requested_start_y=float(start_y),
            requested_end_x=float(end_x),
            requested_end_y=float(end_y),
            start_x=80,
            start_y=150,
            end_x=20,
            end_y=50,
            width=100,
            height=200,
            duration_ms=int(duration_ms),
        )


def test_initialize_and_tools_list_do_not_connect_to_device():
    created = {'count': 0}

    def factory():
        created['count'] += 1
        return FakeDevice()

    server = AndroidAccessMcpServer(device_factory=factory)

    initialize = server.handle_message(
        {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {}}
    )
    tools = server.handle_message(
        {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list', 'params': {}}
    )

    assert initialize['result']['capabilities'] == {'tools': {}}
    assert [tool['name'] for tool in tools['result']['tools']] == [
        'current_screen',
        'click',
        'swipe',
    ]
    assert created['count'] == 0


def test_click_tool_returns_actual_coordinate_payload():
    fake_device = FakeDevice()
    server = AndroidAccessMcpServer(device_factory=lambda: fake_device)

    response = server.handle_message(
        {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'tools/call',
            'params': {'name': 'click', 'arguments': {'x': 0.1, 'y': 0.2}},
        }
    )

    content = response['result']['content']
    payload = json.loads(content[0]['text'])
    assert payload['x'] == 10
    assert payload['y'] == 20
    assert payload['serial'] == 'phone-1'
    assert fake_device.clicks == [(0.1, 0.2)]


def test_swipe_tool_returns_actual_coordinate_payload():
    fake_device = FakeDevice()
    server = AndroidAccessMcpServer(device_factory=lambda: fake_device)

    response = server.handle_message(
        {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'tools/call',
            'params': {
                'name': 'swipe',
                'arguments': {
                    'start_x': 0.8,
                    'start_y': 0.75,
                    'end_x': 0.2,
                    'end_y': 0.25,
                    'duration_ms': 400,
                },
            },
        }
    )

    content = response['result']['content']
    payload = json.loads(content[0]['text'])
    assert payload['start_x'] == 80
    assert payload['start_y'] == 150
    assert payload['end_x'] == 20
    assert payload['end_y'] == 50
    assert payload['duration_ms'] == 400
    assert payload['serial'] == 'phone-1'
    assert fake_device.swipes == [(0.8, 0.75, 0.2, 0.25, 400)]


def test_current_screen_tool_returns_text_and_image_content():
    server = AndroidAccessMcpServer(device_factory=FakeDevice)

    response = server.handle_message(
        {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'tools/call',
            'params': {
                'name': 'current_screen',
                'arguments': {'max_height': 100, 'width': 20, 'height': 40},
            },
        }
    )

    content = response['result']['content']
    metadata = json.loads(content[0]['text'])
    assert metadata['width'] == 20
    assert metadata['height'] == 40
    assert metadata['serial'] == 'phone-1'
    assert content[1] == {
        'type': 'image',
        'data': 'fakepng',
        'mimeType': 'image/png',
    }
