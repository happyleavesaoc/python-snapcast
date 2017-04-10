import unittest
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
        self.stream = Snapstream(data)

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
