import asyncio
import json
import random


def jsonrpc_request(method, identifier, params=None):
    return '{}\r\n'.format(json.dumps({
        'id': identifier,
        'method': method,
        'params': params or {},
        'jsonrpc': '2.0'
    })).encode()


class SnapcastProtocol(asyncio.Protocol):

    def __init__(self, loop, callbacks):
        self._buffer = {}
        self._callbacks = callbacks

    def connection_made(self, transport):
        self._transport = transport

    def data_received(self, data):
        for cmd in data.decode().strip().split('\r\n'):
            data = json.loads(cmd)
            if not isinstance(data, list):
                data = [data]
            for item in data:
                self.handle_data(item)

    def handle_data(self, data):
        if 'id' in data:
            self.handle_response(data)
        else:
            self.handle_notification(data)

    def handle_response(self, data):
        identifier = data.get('id')
        self._buffer[identifier]['data'] = data.get('result')
        self._buffer[identifier]['flag'].set()

    def handle_notification(self, data):
        if data.get('method') in self._callbacks:
            self._callbacks.get(data.get('method'))(data.get('result'))

    @asyncio.coroutine
    def request(self, method, params):
        identifier = random.randint(1, 1000)
        self._transport.write(jsonrpc_request(method, identifier, params))
        self._buffer[identifier] = {'flag': asyncio.Event()}
        yield from self._buffer[identifier]['flag'].wait()
        result = self._buffer[identifier]['data']
        del self._buffer[identifier]['data']
        return result
