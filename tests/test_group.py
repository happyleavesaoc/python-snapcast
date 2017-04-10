import unittest
from unittest.mock import Mock
from helpers.mock_snapcast import MockServer
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
        self.group = Snapgroup(MockServer(), data)

    def test_init(self):
        self.assertEqual(self.group.identifier, 'test')
        self.assertEqual(self.group.name, '')
        self.assertEqual(self.group.friendly_name, 'test stream')
        self.assertEqual(self.group.stream, 'test stream')
        self.assertEqual(self.group.muted, False)
        self.assertEqual(self.group.clients, ['a', 'b'])
        self.assertEqual(self.group.stream_status, 'playing')

    def test_update(self):
        self.group.update({
            'stream_id': 'other stream'
        })
        self.assertEqual(self.group.stream, 'other stream')

    def test_set_muted(self):
        self.group.muted = True
        self.assertEqual(self.group.muted, True)

    def test_add_client(self):
        self.group.add_client('c')
        # TODO: add assert

    def test_remove_client(self):
        self.group.remove_client('a')
        # TODO: add assert

    def test_streams_by_name(self):
        self.assertEqual(self.group.streams_by_name().keys(), set(['test stream']))

    def test_update_mute(self):
        self.group.update_mute({'mute': True})
        self.assertEqual(self.group.muted, True)

    def test_update_stream(self):
        self.group.update_stream({'stream_id': 'other stream'})
        self.assertEqual(self.group.stream, 'other stream')

    def test_set_callback(self):
        cb = Mock()
        self.group.set_callback(cb)
        self.group.update_mute({'mute': True})
        self.assertTrue(cb.called)
