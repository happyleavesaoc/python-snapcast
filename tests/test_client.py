import unittest
from unittest import mock
from unittest.mock import MagicMock, AsyncMock
from helpers import async_run

from snapcast.control.client import Snapclient


class TestSnapclient(unittest.TestCase):

    def setUp(self):
        data = {
            'id': 'test',
            'host': {
                'ip': '0.0.0.0',
                'name': 'localhost'
            },
            'config': {
                'name': '',
                'latency': 0,
                'volume': {
                    'muted': False,
                    'percent': 90
                }
            },
            'snapclient': {
                'version': '0.0'
            },
            'connected': True
        }
        server = AsyncMock()
        server.synchronize = MagicMock()
        group = AsyncMock()
        group.callback = MagicMock()
        server.group = MagicMock(return_value=group)
        server.groups = ['test_group']
        self.client = Snapclient(server, data)

    @mock.patch.object(Snapclient, 'group', new=1)
    def test_init(self):
        self.assertEqual(self.client.identifier, 'test')
        self.assertEqual(self.client.friendly_name, 'localhost')
        self.assertEqual(self.client.version, '0.0')
        self.assertEqual(self.client.connected, True)
        self.assertEqual(self.client.name, '')
        self.assertEqual(self.client.latency, 0)
        self.assertEqual(self.client.volume, 90)
        self.assertEqual(self.client.muted, False)
        self.assertEqual(self.client.group, 1)

    @mock.patch.object(Snapclient, 'group')
    def test_set_volume(self, mock):
        async_run(self.client.set_volume(100))
        self.assertEqual(self.client.volume, 100)

    def test_set_name(self):
        async_run(self.client.set_name('test'))
        self.assertEqual(self.client.name, 'test')

    def test_set_latency(self):
        async_run(self.client.set_latency(1))
        self.assertEqual(self.client.latency, 1)

    def test_set_muted(self):
        async_run(self.client.set_muted(True))
        self.assertEqual(self.client.muted, True)

    @mock.patch.object(Snapclient, 'group')
    def test_update_volume(self, mock):
        self.client.update_volume({'volume': {'percent': 50, 'muted': True}})
        self.assertEqual(self.client.volume, 50)
        self.assertEqual(self.client.muted, True)

    def test_update_name(self):
        self.client.update_name({'name': 'new name'})
        self.assertEqual(self.client.name, 'new name')

    def test_update_latency(self):
        self.client.update_latency({'latency': 50})
        self.assertEqual(self.client.latency, 50)

    def test_update_connected(self):
        self.client.update_connected(False)
        self.assertEqual(self.client.connected, False)

    @mock.patch.object(Snapclient, 'group')
    def test_snapshot_restore(self, mock):
        async_run(self.client.set_name('first'))
        self.client.snapshot()
        async_run(self.client.set_name('other name'))
        self.assertEqual(self.client.name, 'other name')
        async_run(self.client.restore())
        self.assertEqual(self.client.name, 'first')

    def test_set_callback(self):
        cb = MagicMock()
        self.client.set_callback(cb)
        self.client.update_connected(False)
        cb.assert_called_with(self.client)

    def test_groups_available(self):
        self.assertEqual(self.client.groups_available(), ['test_group'])
