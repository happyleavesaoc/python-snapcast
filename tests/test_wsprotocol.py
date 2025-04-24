import unittest
import asyncio
from unittest.mock import MagicMock, patch

from snapcast.control.protocol import jsonrpc_request
from snapcast.control.wsprotocol import SnapcastWebSocketProtocol

class TestSnapcastProtocol(unittest.TestCase):
    def setUp(self):
        self.websocket = MagicMock()
        self.callbacks = {
            'Server.OnDisconnect': MagicMock()
        }
        self.protocol = SnapcastWebSocketProtocol(self.websocket, self.callbacks)

    def test_jsonrpc_request(self):
        method = 'Server.GetStatus'
        identifier = 123
        params = {'param1': 'value1'}
        expected_request = '{"id": 123, "method": "Server.GetStatus", "params": {"param1": "value1"}, "jsonrpc": "2.0"}\r\n'.encode()
        request = jsonrpc_request(method, identifier, params)
        self.assertEqual(request, expected_request)

    def test_handle_response(self):
        response_data = {
            'id': 123,
            'result': {'status': 'ok'},
            'error': None
        }
        self.protocol.handle_data(response_data)
        self.assertTrue(self.protocol._buffer[123]['flag'].is_set())
        self.assertEqual(self.protocol._buffer[123]['data'], {'status': 'ok'})
        self.assertIsNone(self.protocol._buffer[123]['error'])

    def test_handle_notification(self):
        notification_data = {
            'method': 'Server.OnDisconnect',
            'params': {'client': 'client1'}
        }
        self.protocol.handle_data(notification_data)
        self.callbacks['Server.OnDisconnect'].assert_called_with({'client': 'client1'})

    @patch('snapcast.control.protocol.jsonrpc_request')
    def test_request(self, mock_jsonrpc_request):
        mock_jsonrpc_request.return_value = b'{"id": 123, "method": "Server.GetStatus", "params": {}, "jsonrpc": "2.0"}\r\n'
        self.protocol._buffer[123] = {'flag': asyncio.Event(), 'data': {'status': 'ok'}, 'error': None}

        loop = asyncio.new_event_loop()
        result, error = loop.run_until_complete(self.protocol.request('Server.GetStatus', {}))
        self.assertEqual(result, {'status': 'ok'})
        self.assertIsNone(error)
