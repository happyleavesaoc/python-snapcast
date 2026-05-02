"""Snapcast protocol."""

import asyncio
import json
import threading

SERVER_ONDISCONNECT = 'Server.OnDisconnect'


# pylint: disable=consider-using-f-string
def jsonrpc_request(method, identifier, params=None):
    """Produce a JSONRPC request."""
    return '{}\r\n'.format(json.dumps({
        'id': identifier,
        'method': method,
        'params': params or {},
        'jsonrpc': '2.0'
    })).encode()


class SnapcastProtocol(asyncio.Protocol):
    """Async Snapcast protocol."""

    def __init__(self, callbacks):
        """Initialize."""
        self._transport = None
        self._buffer = {}
        self._callbacks = callbacks
        self._data_buffer = ''
        self._next_id_lock = threading.Lock()
        self._next_id_value = 0

    def connection_made(self, transport):
        """When a connection is made."""
        self._transport = transport

    def connection_lost(self, exc):
        """When a connection is lost."""
        for b in self._buffer.values():
            b['error'] = {"code": -1, "message": "connection lost"}
            b['flag'].set()
        self._callbacks.get(SERVER_ONDISCONNECT)(exc)

    def data_received(self, data):
        """Handle received data."""
        self._data_buffer += data.decode()
        if not self._data_buffer.endswith('\r\n'):
            return
        data = self._data_buffer
        self._data_buffer = ''  # clear buffer
        for cmd in data.strip().split('\r\n'):
            data = json.loads(cmd)
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
        entry = self._buffer.get(identifier)
        if entry is None:
            # late/orphan response: request was cancelled, connection was
            # re-established, or another response with the same id already
            # ran cleanup. Drop silently.
            return
        entry['data'] = data.get('result')
        entry['error'] = data.get('error')
        entry['flag'].set()

    def handle_notification(self, data):
        """Handle JSONRPC notification."""
        if data.get('method') in self._callbacks:
            self._callbacks.get(data.get('method'))(data.get('params'))

    def _next_request_id(self) -> int:
        """Allocate a unique JSON-RPC request id.

        Explicit lock keeps allocation correct under both GIL and free-threaded
        (PEP 703) CPython. itertools.count() atomicity is implementation-defined.
        """
        with self._next_id_lock:
            self._next_id_value += 1
            return self._next_id_value

    async def request(self, method, params):
        """Send a JSONRPC request."""
        identifier = self._next_request_id()
        self._transport.write(jsonrpc_request(method, identifier, params))
        self._buffer[identifier] = {'flag': asyncio.Event()}
        try:
            await self._buffer[identifier]['flag'].wait()
            result = self._buffer[identifier].get('data')
            error = self._buffer[identifier].get('error')
            return (result, error)
        finally:
            self._buffer.pop(identifier, None)
