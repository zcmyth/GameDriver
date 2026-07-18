from __future__ import annotations

import json
import logging
import sys
from dataclasses import asdict
from typing import Any, Callable

from android_access_mcp import __version__
from android_access_mcp.device import AndroidDevice


JsonObject = dict[str, Any]
DeviceFactory = Callable[[], AndroidDevice]


class McpError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class AndroidAccessMcpServer:
    def __init__(self, device_factory: DeviceFactory | None = None):
        self._device_factory = device_factory or AndroidDevice
        self._device: AndroidDevice | None = None

    @property
    def device(self) -> AndroidDevice:
        if self._device is None:
            self._device = self._device_factory()
        return self._device

    def handle_message(self, message: Any) -> Any:
        if isinstance(message, list):
            responses = [
                response
                for item in message
                if (response := self._handle_single_message(item)) is not None
            ]
            return responses or None
        return self._handle_single_message(message)

    def _handle_single_message(self, message: Any) -> JsonObject | None:
        if not isinstance(message, dict):
            return self._error_response(None, -32600, 'Invalid Request')

        request_id = message.get('id')
        method = message.get('method')
        if method is None:
            return self._error_response(request_id, -32600, 'Missing method')

        if method.startswith('notifications/'):
            return None

        try:
            result = self._dispatch(method, message.get('params') or {})
        except McpError as error:
            return self._error_response(request_id, error.code, error.message)
        except Exception as error:
            logging.exception('Unhandled MCP request failure')
            return self._error_response(request_id, -32603, str(error))

        if request_id is None:
            return None

        return {'jsonrpc': '2.0', 'id': request_id, 'result': result}

    def _dispatch(self, method: str, params: JsonObject) -> JsonObject:
        if method == 'initialize':
            return self._initialize(params)
        if method == 'ping':
            return {}
        if method == 'tools/list':
            return {'tools': self._tools()}
        if method == 'tools/call':
            return self._call_tool(params)
        raise McpError(-32601, f'Method not found: {method}')

    def _initialize(self, params: JsonObject) -> JsonObject:
        return {
            'protocolVersion': params.get('protocolVersion') or '2024-11-05',
            'capabilities': {'tools': {}},
            'serverInfo': {
                'name': 'android-access-mcp',
                'version': __version__,
            },
        }

    def _tools(self) -> list[JsonObject]:
        return [
            {
                'name': 'current_screen',
                'description': (
                    'Capture the current Android screen as PNG image content. '
                    'Requires an ADB-visible Android device.'
                ),
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'max_height': {
                            'type': 'integer',
                            'minimum': 1,
                            'description': (
                                'Optional maximum returned image height. '
                                'Omit for full resolution.'
                            ),
                        },
                        'width': {
                            'type': 'integer',
                            'minimum': 1,
                            'description': (
                                'Optional returned image width. If height is also '
                                'provided, returns exactly width x height.'
                            ),
                        },
                        'height': {
                            'type': 'integer',
                            'minimum': 1,
                            'description': (
                                'Optional returned image height. If width is also '
                                'provided, returns exactly width x height.'
                            ),
                        },
                    },
                    'additionalProperties': False,
                },
            },
            {
                'name': 'click',
                'description': (
                    'Click an Android screen coordinate. Values from 0 to 1 are '
                    'normalized to the current window size; other values are pixels.'
                ),
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'x': {
                            'type': 'number',
                            'description': 'Normalized or absolute x coordinate.',
                        },
                        'y': {
                            'type': 'number',
                            'description': 'Normalized or absolute y coordinate.',
                        },
                    },
                    'required': ['x', 'y'],
                    'additionalProperties': False,
                },
            },
            {
                'name': 'swipe',
                'description': (
                    'Swipe or drag from one Android screen coordinate to another. '
                    'Values from 0 to 1 are normalized to the current window size; '
                    'other values are pixels.'
                ),
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'start_x': {
                            'type': 'number',
                            'description': (
                                'Normalized or absolute starting x coordinate.'
                            ),
                        },
                        'start_y': {
                            'type': 'number',
                            'description': (
                                'Normalized or absolute starting y coordinate.'
                            ),
                        },
                        'end_x': {
                            'type': 'number',
                            'description': (
                                'Normalized or absolute ending x coordinate.'
                            ),
                        },
                        'end_y': {
                            'type': 'number',
                            'description': (
                                'Normalized or absolute ending y coordinate.'
                            ),
                        },
                        'duration_ms': {
                            'type': 'integer',
                            'minimum': 1,
                            'default': 300,
                            'description': 'Gesture duration in milliseconds.',
                        },
                    },
                    'required': ['start_x', 'start_y', 'end_x', 'end_y'],
                    'additionalProperties': False,
                },
            },
            {
                'name': 'back',
                'description': 'Press the Android Back key.',
                'inputSchema': {
                    'type': 'object',
                    'properties': {},
                    'additionalProperties': False,
                },
            },
        ]

    def _call_tool(self, params: JsonObject) -> JsonObject:
        name = params.get('name')
        arguments = params.get('arguments') or {}
        if not isinstance(arguments, dict):
            raise McpError(-32602, 'Tool arguments must be an object')

        if name == 'current_screen':
            return self._current_screen(arguments)
        if name == 'click':
            return self._click(arguments)
        if name == 'swipe':
            return self._swipe(arguments)
        if name == 'back':
            return self._back()
        raise McpError(-32602, f'Unknown tool: {name}')

    def _current_screen(self, arguments: JsonObject) -> JsonObject:
        result = self.device.current_screen(
            max_height=arguments.get('max_height'),
            width=arguments.get('width'),
            height=arguments.get('height'),
        )
        payload = asdict(result)
        text = json.dumps(
            {
                'width': result.width,
                'height': result.height,
                'original_width': result.original_width,
                'original_height': result.original_height,
                'serial': self.device.serial,
            },
            separators=(',', ':'),
        )
        return {
            'content': [
                {'type': 'text', 'text': text},
                {
                    'type': 'image',
                    'data': payload['png_base64'],
                    'mimeType': 'image/png',
                },
            ],
            'isError': False,
        }

    def _click(self, arguments: JsonObject) -> JsonObject:
        missing = [key for key in ('x', 'y') if key not in arguments]
        if missing:
            raise McpError(-32602, f'Missing required argument: {", ".join(missing)}')

        result = self.device.click(arguments['x'], arguments['y'])
        text = json.dumps(
            {**asdict(result), 'serial': self.device.serial},
            separators=(',', ':'),
        )
        return {
            'content': [{'type': 'text', 'text': text}],
            'isError': False,
        }

    def _swipe(self, arguments: JsonObject) -> JsonObject:
        required = ('start_x', 'start_y', 'end_x', 'end_y')
        missing = [key for key in required if key not in arguments]
        if missing:
            raise McpError(-32602, f'Missing required argument: {", ".join(missing)}')

        result = self.device.swipe(
            arguments['start_x'],
            arguments['start_y'],
            arguments['end_x'],
            arguments['end_y'],
            duration_ms=arguments.get('duration_ms', 300),
        )
        text = json.dumps(
            {**asdict(result), 'serial': self.device.serial},
            separators=(',', ':'),
        )
        return {
            'content': [{'type': 'text', 'text': text}],
            'isError': False,
        }

    def _back(self) -> JsonObject:
        result = self.device.back()
        text = json.dumps(
            {**asdict(result), 'serial': self.device.serial},
            separators=(',', ':'),
        )
        return {
            'content': [{'type': 'text', 'text': text}],
            'isError': False,
        }

    @staticmethod
    def _error_response(request_id: Any, code: int, message: str) -> JsonObject:
        return {
            'jsonrpc': '2.0',
            'id': request_id,
            'error': {
                'code': code,
                'message': message,
            },
        }


def run_stdio(server: AndroidAccessMcpServer | None = None) -> int:
    server = server or AndroidAccessMcpServer()
    for line in sys.stdin.buffer:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
            response = server.handle_message(message)
        except json.JSONDecodeError as error:
            response = AndroidAccessMcpServer._error_response(
                None,
                -32700,
                f'Parse error: {error}',
            )

        if response is not None:
            sys.stdout.write(json.dumps(response, separators=(',', ':')) + '\n')
            sys.stdout.flush()

    return 0


def main() -> int:
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    return run_stdio()


if __name__ == '__main__':
    raise SystemExit(main())
