"""Regression tests for state corruption on failed stream selection."""

import asyncio
import unittest
from unittest.mock import AsyncMock

from snapcast.control.exceptions import SnapcastRequestError
from snapcast.control.group import Snapgroup


class TestRejectedStream(unittest.TestCase):
    def setUp(self):
        self.server = AsyncMock()
        self.group = Snapgroup(self.server, {
            'id': 'group', 'name': 'Group', 'clients': [],
            'stream_id': 'external-radio', 'muted': False,
        })

    def test_rejection_preserves_previous_stream(self):
        error = {'code': -32603, 'message': 'Internal error',
                 'data': 'Stream not found'}
        self.server.group_stream.return_value = error
        with self.assertRaises(SnapcastRequestError) as raised:
            asyncio.run(self.group.set_stream('missing'))
        self.assertEqual(raised.exception.code, -32603)
        self.assertEqual(raised.exception.error, error)
        self.assertEqual(self.group.stream, 'external-radio')

    def test_transport_exception_preserves_previous_stream(self):
        self.server.group_stream.side_effect = OSError('disconnected')
        with self.assertRaises(OSError):
            asyncio.run(self.group.set_stream('missing'))
        self.assertEqual(self.group.stream, 'external-radio')

    def test_success_updates_cache_after_response(self):
        async def select(identifier, stream_id):
            self.assertEqual(self.group.stream, 'external-radio')
            return stream_id
        self.server.group_stream.side_effect = select
        asyncio.run(self.group.set_stream('new-radio'))
        self.assertEqual(self.group.stream, 'new-radio')


class TestRejectedStreamOverTcp(unittest.IsolatedAsyncioTestCase):
    async def test_jsonrpc_error_does_not_change_group_state(self):
        import json
        from snapcast.control.server import Snapserver
        writers = []
        async def serve(reader, writer):
            writers.append(writer)
            try:
                while line := await reader.readline():
                    request = json.loads(line)
                    response = {'id': request['id'], 'jsonrpc': '2.0'}
                    if request['method'] == 'Server.GetStatus':
                        response['result'] = {'server': {
                            'server': {'snapserver': {'version': '0.35.0'}},
                            'groups': [{'id': 'group', 'name': 'Group', 'clients': [],
                                        'stream_id': 'external-radio', 'muted': False}],
                            'streams': [],
                        }}
                    else:
                        response['error'] = {'code': -32603, 'message': 'Internal error',
                                             'data': 'Stream not found'}
                    writer.write((json.dumps(response) + '\r\n').encode())
                    await writer.drain()
            finally:
                writer.close()
        listener = await asyncio.start_server(serve, '127.0.0.1', 0)
        server = Snapserver(asyncio.get_running_loop(), '127.0.0.1',
                            listener.sockets[0].getsockname()[1])
        try:
            await asyncio.wait_for(server.start(), 1)
            with self.assertRaises(SnapcastRequestError):
                await asyncio.wait_for(server.group('group').set_stream('missing'), 1)
            self.assertEqual(server.group('group').stream, 'external-radio')
        finally:
            server.stop()
            listener.close()
            await listener.wait_closed()
            for writer in writers:
                writer.close()
                await writer.wait_closed()
