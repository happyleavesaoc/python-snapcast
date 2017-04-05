import unittest
from helpers.mock_telnet import MockTelnet
from snapcast.control import Snapserver


class TestSnapserver(unittest.TestCase):

    def setUp(self):
        self.server = Snapserver('0.0.0.0')

    def test_init(self):
        self.assertEqual(self.server.version, 0.11)
        self.assertEqual(len(self.server.clients), 1)
        self.assertEqual(len(self.server.groups), 1)
        self.assertEqual(len(self.server.streams), 1)
        self.assertEqual(self.server.group('test').identifier, 'test')
        self.assertEqual(self.server.stream('stream').identifier, 'stream')
        self.assertEqual(self.server.client('test').identifier, 'test')

    def test_status(self):
        status = self.server.status()
        self.assertEqual(status.get('server').get('version'), 0.11)

    def test_rpc_version(self):
        self.assertEqual(self.server.rpc_version(), {'major': 2, 'minor': 0, 'patch': 0})

    def test_client_name(self):
        self.assertEqual('test name', self.server.client_name('test', 'test name'))

    def test_client_set_invalid(self):
        self.server.client_name('efgh', 'test name')
        # TODO: add assert

    def test_delete_client(self):
        self.server.delete_client('test')
        self.assertEqual(len(self.server.clients), 0)

    def test_client_name(self):
        self.assertEqual(self.server.client_name('test', 'new name'), 'new name')

    def test_client_latency(self):
        self.assertEqual(self.server.client_latency('test', 50), 50)

    def test_client_volume(self):
        vol = {'percent': 50, 'muted': True}
        self.assertEqual(self.server.client_volume('test', vol), vol)

    def test_client_status(self):
        self.assertEqual(self.server.client_status('test'), {'config': {}})

    def test_group_status(self):
        self.assertEqual(self.server.group_status('test'), {'clients': []})

    def test_group_mute(self):
        self.assertEqual(self.server.group_mute('test', True), True)

    def test_group_stream(self):
        self.assertEqual(self.server.group_stream('test', 'stream'), 'stream')

    def test_group_clients(self):
        self.assertEqual(self.server.group_clients('test', ['test']), ['test'])

    def test_synchronize(self):
        status = self.server.status()
        status['server']['version'] = '0.12'
        self.server.synchronize(status)
        self.assertEqual(self.server.version, '0.12')

    def test_invalid_event(self):
        with self.assertRaises(ValueError):
            self.server._on_event({'method': 'bad'})

    def test_on_server_update(self):
        status = self.server.status()
        status['server']['version'] = '0.12'
        self.server._on_server_update(status)
        self.assertEqual(self.server.version, '0.12')

    def test_on_group_mute(self):
        data = {
            'id': 'test',
            'mute': True
        }
        self.server._on_group_mute(data)
        self.assertEqual(self.server.group('test').muted, True)

    def test_on_group_stream_changed(self):
        data = {
            'id': 'test',
            'stream_id': 'other'
        }
        self.server._on_group_stream_changed(data)
        self.assertEqual(self.server.group('test').stream, 'other')

    def test_on_client_connect(self):
        data = {
            'id': 'new',
            'client': {
                'id': 'new',
                'connected': True,
                'config': {
                    'name': ''
                },
                'host': {
                    'name': 'new'
                }
            }
        }
        self.server._on_client_connect(data)
        self.assertEqual(self.server.client('new').connected, True)

    def test_on_client_disconnect(self):
        data = {
            'id': 'test'
        }
        self.server._on_client_disconnect(data)
        self.assertEqual(self.server.client('test').connected, False)

    def test_on_client_volume_changed(self):
        data = {
            'id': 'test',
            'volume': {
                'percent': 50,
                'muted': True
            }
        }
        self.server._on_client_volume_changed(data)
        self.assertEqual(self.server.client('test').volume, 50)
        self.assertEqual(self.server.client('test').muted, True)

    def test_on_client_name_changed(self):
        data = {
            'id': 'test',
            'name': 'new'
        }
        self.server._on_client_name_changed(data)
        self.assertEqual(self.server.client('test').name, 'new')

    def test_on_client_latency_changed(self):
        data = {
            'id': 'test',
            'latency': 50
        }
        self.server._on_client_latency_changed(data)
        self.assertEqual(self.server.client('test').latency, 50)

    def test_on_stream_update(self):
        data = {
            'id': 'stream',
            'stream': {
                'id': 'stream',
                'status': 'idle',
                'uri': {
                    'query': {
                        'name': 'stream'
                    }
                }
            }
        }
        self.server._on_stream_update(data)
        self.assertEqual(self.server.stream('stream').status, 'idle')
