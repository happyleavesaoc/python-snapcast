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
            },
            'meta': {
                'TITLE': 'Happy!',
            }
        }
        self.stream = Snapstream(data)

    def test_init(self):
        self.assertEqual(self.stream.identifier, 'test')
        self.assertEqual(self.stream.status, 'playing')
        self.assertEqual(self.stream.name, '')
        self.assertEqual(self.stream.friendly_name, 'test')
        self.assertDictEqual(self.stream.meta, {'TITLE': 'Happy!'})

    def test_update(self):
        self.stream.update({
            'id': 'test',
            'status': 'idle'
        })
        self.assertEqual(self.stream.status, 'idle')

    def test_update_meta(self):
        self.stream.update_meta({
            'TITLE': 'Unhappy!'
        })
        self.assertDictEqual(self.stream.meta, {
            'TITLE': 'Unhappy!'
        })
        # Verify that other attributes are still present
        self.assertEqual(self.stream.status, 'playing')