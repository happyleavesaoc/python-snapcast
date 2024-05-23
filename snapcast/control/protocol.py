"""Snapcast protocol."""

import asyncio
import json
import random

SERVER_ONDISCONNECT = 'Server.OnDisconnect'


def jsonrpc_request(method, identifier, params=None):
    """Produce a JSONRPC request.

    Args:
        method (str): The method name to be invoked.
        identifier (int): The unique identifier for the request.
        params (dict, optional): The parameters for the method. Defaults to None.

    Returns:
        bytes: The JSONRPC request in bytes.
    """
    return '{}\r\n'.format(json.dumps({
        'id': identifier,
        'method': method,
        'params': params or {},
        'jsonrpc': '2.0'
    })).encode()


class SnapcastProtocol(asyncio.Protocol):
    """Async Snapcast protocol."""

    def __init__(self, callbacks):
        """Initialize the SnapcastProtocol.

        Args:
            callbacks (dict): A dictionary of callback functions for various events.
        """
        self._transport = None
        self._buffer = {}
        self._callbacks = callbacks
        self._data_buffer = ''

    def connection_made(self, transport):
        """Handle a new connection.

        Args:
            transport (asyncio.Transport): The transport representing the connection.
        """
        self._transport = transport

    def connection_lost(self, exc):
        """Handle a lost connection.

        Args:
            exc (Exception): The exception that caused the connection to be lost.
        """
        for b in self._buffer.values():
            b['error'] = {"code": -1, "message": "connection lost"}
            b['flag'].set()
        if SERVER_ONDISCONNECT in self._callbacks:
            self._callbacks[SERVER_ONDISCONNECT](exc)

    def data_received(self, data):
        """Handle received data.

        Args:
            data (bytes): The data received from the connection.
        """
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
        """Handle JSONRPC data.

        Args:
            data (dict): The JSONRPC data to handle.
        """
        if 'id' in data:
            self.handle_response(data)
        else:
            self.handle_notification(data)

    def handle_response(self, data):
        """Handle JSONRPC response.

        Args:
            data (dict): The JSONRPC response data.
        """
        identifier = data.get('id')
        self._buffer[identifier]['data'] = data.get('result')
        self._buffer[identifier]['error'] = data.get('error')
        self._buffer[identifier]['flag'].set()

    def handle_notification(self, data):
        """Handle JSONRPC notification.

        Args:
            data (dict): The JSONRPC notification data.
        """
        if data.get('method') in self._callbacks:
            self._callbacks[data.get('method')](data.get('params'))

    async def request(self, method, params):
        """Send a JSONRPC request.

        Args:
            method (str): The method name to be invoked.
            params (dict): The parameters for the method.

        Returns:
            tuple: A tuple containing the result and error (if any) of the request.
        """
        identifier = random.randint(1, 1000)
        self._transport.write(jsonrpc_request(method, identifier, params))
        self._buffer[identifier] = {'flag': asyncio.Event()}
        await self._buffer[identifier]['flag'].wait()
        result = self._buffer[identifier].get('data')
        error = self._buffer[identifier].get('error')
        self._buffer[identifier].clear()
        del self._buffer[identifier]
        return result, error
