import unittest
from unittest.mock import Mock
from helpers.mock_snapcast import MockServer
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
        self.client = Snapclient(MockServer(), data)

    def test_init(self):
        self.assertEqual(self.client.identifier, 'test')
        self.assertEqual(self.client.friendly_name, 'localhost')
        self.assertEqual(self.client.version, '0.0')
        self.assertEqual(self.client.connected, True)
        self.assertEqual(self.client.name, '')
        self.assertEqual(self.client.latency, 0)
        self.assertEqual(self.client.volume, 90)
        self.assertEqual(self.client.muted, False)

    def test_set_volume(self):
        self.client.volume = 100
        self.assertEqual(self.client.volume, 100)

    def test_set_name(self):
        self.client.name = 'test'
        self.assertEqual(self.client.name, 'test')

    def test_set_latency(self):
        self.client.latency = 1
        self.assertEqual(self.client.latency, 1)

    def test_set_muted(self):
        self.client.muted = True
        self.assertEqual(self.client.muted, True)

    def test_update_volume(self):
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

    def test_set_callback(self):
        cb = Mock()
        self.client.set_callback(cb)
        self.client.update_connected(False)
        self.assertTrue(cb.called)
