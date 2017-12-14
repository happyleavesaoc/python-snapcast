import unittest
from unittest.mock import MagicMock
from snapcast.control.stream import Snapstream


class TestSnapstream(unittest.TestCase):

    def setUp(self):
        data = {
            'id': 'test',
            'status': 'playing',
            'uri': {
                'query': {
                    'name': ''
                }
            }
        }
        server = MagicMock()
        self.stream = Snapstream(server, data)

    def test_init(self):
        self.assertEqual(self.stream.identifier, 'test')
        self.assertEqual(self.stream.status, 'playing')
        self.assertEqual(self.stream.name, '')
        self.assertEqual(self.stream.friendly_name, 'test')

    def test_update(self):
        self.stream.update({
            'id': 'test',
            'status': 'idle'
        })
        self.assertEqual(self.stream.status, 'idle')
