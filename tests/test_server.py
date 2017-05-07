import asyncio
import copy
import unittest
from unittest import mock
from helpers import AsyncMock

from snapcast.control.server import Snapserver
from snapcast.control import create_server


return_values = {
    'Server.GetStatus': {
        'server': {
            'version': 0.11,
            'groups': [
                {
                    'id': 'test',
                    'stream_id': 'stream',
                    'clients': [
                        {
                            'id': 'test',
                            'host': {
                                'mac': 'abcd',
                                'ip': '0.0.0.0',
                            },
                            'config': {
                                'name': '',
                                'latency': 0,
                                'volume': {
                                    'muted': False,
                                    'percent': 90
                                }
                            },
                            'lastSeen': {
                                'sec': 10,
                                'usec': 100
                            },
                            'snapclient': {
                                'version': '0.0'
                            },
                            'connected': True
                        }
                    ]
                }
            ],
            'streams': [
                {
                    'id': 'stream',
                    'status': 'playing',
                    'uri': {
                        'query': {
                            'name': 'stream'
                        }
                    }
                }
            ]
        }
    },
    'Client.SetName': {
        'name': 'test name'
    },
    'Server.GetRPCVersion': {
        'major': 2,
        'minor': 0,
        'patch': 1
    },
    'Client.SetLatency': {
        'latency': 50
    },
    'Client.SetVolume': {
        'volume': {
            'percent': 50,
            'muted': True
        }
    },
    'Server.DeleteClient': {
        'server': {
            'groups': [
              {
                  'clients': []
              }
          ],
          'streams': [
          ]
       }
    },
    'Group.GetStatus': {
        'group': {
            'clients': []
        }
    },
    'Group.SetMute': {
        'mute': True
    },
    'Group.SetStream': {
        'stream_id': 'stream'
    },
    'Group.SetClients': {
        'clients': ['test']
    }
}


def mock_transact(key):
    return AsyncMock(return_value=return_values[key])


class TestSnapserver(unittest.TestCase):

    def _run(self, coro):
        return self.loop.run_until_complete(coro)

    @mock.patch.object(Snapserver, 'start', new=AsyncMock())
    def setUp(self):
        self.loop = asyncio.get_event_loop()
        self.server = self._run(create_server(self.loop, 'abcd'))
        self.server.synchronize(return_values.get('Server.GetStatus'))

    def test_init(self):
        self.assertEqual(self.server.version, 0.11)
        self.assertEqual(len(self.server.clients), 1)
        self.assertEqual(len(self.server.groups), 1)
        self.assertEqual(len(self.server.streams), 1)
        self.assertEqual(self.server.group('test').identifier, 'test')
        self.assertEqual(self.server.stream('stream').identifier, 'stream')
        self.assertEqual(self.server.client('test').identifier, 'test')

    @mock.patch.object(Snapserver, '_transact', new=mock_transact('Server.GetStatus'))
    def test_status(self):
        status = self._run(self.server.status())
        self.assertEqual(status.get('server').get('version'), 0.11)

    @mock.patch.object(Snapserver, '_transact', new=mock_transact('Server.GetRPCVersion'))
    def test_rpc_version(self):
        version = self._run(self.server.rpc_version())
        self.assertEqual(version, {'major': 2, 'minor': 0, 'patch': 1})

    @mock.patch.object(Snapserver, '_transact', new=mock_transact('Client.SetName'))
    def test_client_name(self):
        name = self._run(self.server.client_name('test', 'test name'))
        self.assertEqual(name, 'test name')

    @mock.patch.object(Snapserver, '_transact', new=mock_transact('Client.SetLatency'))
    def test_client_latency(self):
        result = self._run(self.server.client_latency('test', 50))
        self.assertEqual(result, 50)

    @mock.patch.object(Snapserver, '_transact', new=mock_transact('Client.SetVolume'))
    def test_client_volume(self):
        vol = {'percent': 50, 'muted': True}
        result = self._run(self.server.client_volume('test', vol))
        self.assertEqual(result, vol)

    @mock.patch.object(Snapserver, '_transact', new=mock_transact('Server.DeleteClient'))
    def test_delete_client(self):
        self._run(self.server.delete_client('test'))
        self.assertEqual(len(self.server.clients), 0)

    @mock.patch.object(Snapserver, '_transact', new=mock_transact('Group.GetStatus'))
    def test_group_status(self):
        result = self._run(self.server.group_status('test'))
        self.assertEqual(result, {'clients': []})

    @mock.patch.object(Snapserver, '_transact', new=mock_transact('Group.SetMute'))
    def test_group_mute(self):
        result = self._run(self.server.group_mute('test', True))
        self.assertEqual(result, True)

    @mock.patch.object(Snapserver, '_transact', new=mock_transact('Group.SetStream'))
    def test_group_stream(self):
        result = self._run(self.server.group_stream('test', 'stream'))
        self.assertEqual(result, 'stream')

    @mock.patch.object(Snapserver, '_transact', new=mock_transact('Group.SetClients'))
    def test_group_clients(self):
        result = self._run(self.server.group_clients('test', ['test']))
        self.assertEqual(result, ['test'])

    def test_synchronize(self):
        status = copy.deepcopy(return_values.get('Server.GetStatus'))
        status['server']['version'] = '0.12'
        self.server.synchronize(status)
        self.assertEqual(self.server.version, '0.12')

    def test_on_server_connect(self):
        cb = mock.MagicMock()
        self.server.set_on_connect_callback(cb)
        self.server._on_server_connect()
        cb.assert_called()

    def test_on_server_disconnect(self):
        cb = mock.MagicMock()
        self.server.set_on_disconnect_callback(cb)
        e = Exception()
        self.server._on_server_disconnect(e)
        cb.assert_called_with(e)

    def test_on_server_update(self):
        status = copy.deepcopy(return_values.get('Server.GetStatus'))
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
        cb = mock.MagicMock()
        self.server.set_new_client_callback(cb)
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
        cb.assert_called_with(self.server.client('new'))

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
