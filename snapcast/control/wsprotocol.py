"""Snapcast protocol."""

import asyncio
import json
import random

SERVER_ONDISCONNECT = 'Server.OnDisconnect'


def jsonrpc_request(method, identifier, params=None):
    """Produce a JSONRPC request."""
    return '{}\r\n'.format(json.dumps({
        'id': identifier,
        'method': method,
        'params': params or {},
        'jsonrpc': '2.0'
    })).encode()


class SnapcastWebSocketProtocol():
    """Async Snapcast protocol."""

    def __init__(self, websocket, callbacks):
        """Initialize."""
        self._websocket = websocket
        self._callbacks = callbacks
        self._buffer = {}

    def message_received(self, message):
        """Handle received data."""
        data = json.loads(message)
        if not isinstance(data, list):
            data = [data]
        for item in data:
            self.handle_data(item)

    def handle_data(self, data):
        """Handle JSONRPC data."""
        if 'id' in data:
            self.handle_response(data)
        else:
            self.handle_notification(data)

    def handle_response(self, data):
        """Handle JSONRPC response."""
        identifier = data.get('id')
        self._buffer[identifier]['data'] = data.get('result')
        self._buffer[identifier]['error'] = data.get('error')
        self._buffer[identifier]['flag'].set()

    def handle_notification(self, data):
        """Handle JSONRPC notification."""
        if data.get('method') in self._callbacks:
            self._callbacks.get(data.get('method'))(data.get('params'))

    async def request(self, method, params):
        """Send a JSONRPC request."""
        identifier = random.randint(1, 1000)
        await self._websocket.send(jsonrpc_request(method, identifier, params))
        self._buffer[identifier] = {'flag': asyncio.Event()}
        await self._buffer[identifier]['flag'].wait()
        result = self._buffer[identifier]['data']
        error = self._buffer[identifier]['error']
        del self._buffer[identifier]['data']
        del self._buffer[identifier]['error']
        return (result, error)
