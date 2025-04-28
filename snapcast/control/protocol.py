"""Snapcast protocol."""

import asyncio
import json
import random
from typing import Any, Callable, Dict, Optional, Tuple

SERVER_ONDISCONNECT = 'Server.OnDisconnect'

# pylint: disable=consider-using-f-string

def jsonrpc_request(method: str, identifier: int, params: Optional[Dict[str, Any]] = None) -> bytes:
    """Produce a JSONRPC request."""
    return '{}\r\n'.format(json.dumps({
        'id': identifier,
        'method': method,
        'params': params or {},
        'jsonrpc': '2.0'
    })).encode()

class SnapcastProtocol(asyncio.Protocol):
    """Async Snapcast protocol."""

    def __init__(self, callbacks: Dict[str, Callable[[Any], None]]) -> None:
        """Initialize the SnapcastProtocol."""
        self._transport: Optional[asyncio.Transport] = None
        self._buffer: Dict[int, Dict[str, Any]] = {}
        self._callbacks: Dict[str, Callable[[Any], None]] = callbacks
        self._data_buffer: str = ''

    def connection_made(self, transport: asyncio.Transport) -> None:
        """Handle a new connection."""
        self._transport = transport

    def connection_lost(self, exc: Optional[Exception]) -> None:
        """Handle a lost connection."""
        for b in self._buffer.values():
            b['error'] = {"code": -1, "message": "connection lost"}
            b['flag'].set()
        if SERVER_ONDISCONNECT in self._callbacks:
            self._callbacks[SERVER_ONDISCONNECT](exc)

    def data_received(self, data: bytes) -> None:
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

    def handle_data(self, data: Dict[str, Any]) -> None:
        """Handle JSONRPC data."""
        if 'id' in data:
            self.handle_response(data)
        else:
            self.handle_notification(data)

    def handle_response(self, data: Dict[str, Any]) -> None:
        """Handle JSONRPC response."""
        identifier = data.get('id')
        if identifier in self._buffer:
            self._buffer[identifier]['data'] = data.get('result')
            self._buffer[identifier]['error'] = data.get('error')
            self._buffer[identifier]['flag'].set()

    def handle_notification(self, data: Dict[str, Any]) -> None:
        """Handle JSONRPC notification."""
        if data.get('method') in self._callbacks:
            self._callbacks.get(data.get('method'))(data.get('params'))

    async def request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Tuple[Optional[Any], Optional[Dict[str, Any]]]:
        """Send a JSONRPC request."""
        identifier = random.randint(1, 1000)
        self._transport.write(jsonrpc_request(method, identifier, params))
        self._buffer[identifier] = {'flag': asyncio.Event()}
        await self._buffer[identifier]['flag'].wait()
        result = self._buffer[identifier].get('data')
        error = self._buffer[identifier].get('error')
        self._buffer[identifier].clear()
        del self._buffer[identifier]
        return (result, error)
