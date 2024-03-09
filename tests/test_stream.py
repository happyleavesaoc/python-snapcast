import unittest
from snapcast.control.stream import Snapstream


class TestSnapstream(unittest.TestCase):

    def setUp(self):
        data_meta = {
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
        data = {
            'id': 'test',
            'status': 'playing',
            'uri': {
                'path': '/tmp/snapfifo',
                'query': {
                    'name': ''
                }
            },
            'properties': {
                'canControl': False,
                'metadata': {
                    'title': 'Happy!',
                }
            }
        }
        self.stream_meta = Snapstream(data_meta)
        self.stream = Snapstream(data)

    def test_init(self):
        self.assertEqual(self.stream.identifier, 'test')
        self.assertEqual(self.stream.status, 'playing')
        self.assertEqual(self.stream.name, '')
        self.assertEqual(self.stream.friendly_name, 'test')
        self.assertEqual(self.stream.path, '/tmp/snapfifo')
        self.assertDictEqual(self.stream_meta.meta, {'TITLE': 'Happy!'})
        self.assertDictEqual(self.stream.properties['metadata'], {'title': 'Happy!'})
        self.assertDictEqual(self.stream.properties,
                             {'canControl': False, 'metadata': {'title': 'Happy!'}})
        self.assertDictEqual(self.stream.metadata, {'title': 'Happy!'})

    def test_update(self):
        self.stream.update({
            'id': 'test',
            'status': 'idle'
        })
        self.assertEqual(self.stream.status, 'idle')

    def test_update_meta(self):
        self.stream_meta.update_meta({
            'TITLE': 'Unhappy!'
        })
        self.assertDictEqual(self.stream_meta.meta, {
            'TITLE': 'Unhappy!'
        })
        # Verify that other attributes are still present
        self.assertEqual(self.stream.status, 'playing')

    def test_update_metadata(self):
        self.stream.update_metadata({
            'title': 'Unhappy!'
        })
        self.assertDictEqual(self.stream.metadata, {
            'title': 'Unhappy!'
        })
        # Verify that other attributes are still present
        self.assertEqual(self.stream.status, 'playing')

    def test_update_properties(self):
        self.stream.update_properties({
            'canControl': True,
            'metadata': {
                'title': 'Unhappy!',
            }
        })
        self.assertDictEqual(self.stream.properties, {
            'canControl': True,
            'metadata': {
                'title': 'Unhappy!',
            }
        })
        # Verify that other attributes are still present
        self.assertEqual(self.stream.status, 'playing')
