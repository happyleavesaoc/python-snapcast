import unittest
from unittest.mock import MagicMock, AsyncMock
from helpers import async_run

from snapcast.control.group import Snapgroup


class TestSnapgroup(unittest.TestCase):

    def setUp(self):
        data = {
            'id': 'test',
            'name': '',
            'stream_id': 'test stream',
            'muted': False,
            'clients': [
                {'id': 'a'},
                {'id': 'b'}
            ]
        }
        server = AsyncMock()
        server.synchronize = MagicMock()
        stream = MagicMock()
        stream.friendly_name = 'test stream'
        stream.status = 'playing'
        client = AsyncMock()
        client.volume = 50
        client.callback = MagicMock()
        client.update_volume = MagicMock()
        client.friendly_name = 'A'
        client.identifier = 'a'
        server.streams = [stream]
        server.stream = MagicMock(return_value=stream)
        server.client = MagicMock(return_value=client)
        server.clients = [client]
        self.group = Snapgroup(server, data)

    def test_init(self):
        self.assertEqual(self.group.identifier, 'test')
        self.assertEqual(self.group.name, '')
        self.assertEqual(self.group.friendly_name, 'A')
        self.assertEqual(self.group.stream, 'test stream')
        self.assertEqual(self.group.muted, False)
        self.assertEqual(self.group.volume, 50)
        self.assertEqual(self.group.clients, ['a', 'b'])
        self.assertEqual(self.group.stream_status, 'playing')

    def test_repr(self):
        self.assertEqual(self.group.__repr__(), 'Snapgroup (A, test)')

    def test_update(self):
        self.group.update({
            'stream_id': 'other stream'
        })
        self.assertEqual(self.group.stream, 'other stream')

    def test_set_muted(self):
        async_run(self.group.set_muted(True))
        self.assertEqual(self.group.muted, True)

    def test_set_volume(self):
        async_run(self.group.set_volume(75))

    def test_set_stream(self):
        async_run(self.group.set_stream('new stream'))
        self.assertEqual(self.group.stream, 'new stream')

    def test_set_name(self):
        async_run(self.group.set_name('test'))
        self.assertEqual(self.group.name, 'test')

    def test_add_client(self):
        async_run(self.group.add_client('c'))
        # TODO: add assert

    def test_remove_client(self):
        async_run(self.group.remove_client('a'))
        # TODO: add assert

    def test_streams_by_name(self):
        self.assertEqual(self.group.streams_by_name().keys(), set(['test stream']))

    def test_update_mute(self):
        self.group.update_mute({'mute': True})
        self.assertEqual(self.group.muted, True)

    def test_update_stream(self):
        self.group.update_stream({'stream_id': 'other stream'})
        self.assertEqual(self.group.stream, 'other stream')

    def test_snapshot_restore(self):
        async_run(self.group.set_muted(False))
        self.group.snapshot()
        async_run(self.group.set_muted(True))
        self.assertEqual(self.group.muted, True)
        async_run(self.group.restore())
        self.assertEqual(self.group.muted, False)

    def test_set_callback(self):
        cb = MagicMock()
        self.group.set_callback(cb)
        self.group.update_mute({'mute': True})
        cb.assert_called_with(self.group)

    def test_bad_stream_status(self):
        # Simulate a server where the requested stream id is missing
        class DummyClient:
            def __init__(self, identifier, friendly_name):
                self.identifier = identifier
                self.friendly_name = friendly_name

        class DummyServer:
            def __init__(self):
                self._streams = {}
                # provide clients list used by Snapgroup.friendly_name
                self.clients = [DummyClient('a', 'A'), DummyClient('b', 'B')]

            def stream(self, stream_identifier):
                return self._streams[stream_identifier]

            def client(self, identifier):
                # return a client-like object for friendly_name lookup
                for c in self.clients:
                    if c.identifier == identifier:
                        return c
                raise KeyError(identifier)

        # Replace the group's server with the dummy and set an unknown stream id
        self.group._server = DummyServer()

        # Updating the stream should not raise; accessing stream_status should
        # not raise KeyError because the stream id is not present on the server.
        self.group.update_stream({'stream_id': 'no stream'})
        self.assertEqual(self.group.stream_status, 'unknown')

