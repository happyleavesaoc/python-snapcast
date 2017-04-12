import asyncio
import asynctest
import unittest
from unittest import mock
from unittest.mock import Mock
#from helpers.mock_telnet import MockTelnet
from snapcast.control import create_server
from snapcast.control.server import Snapserver


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
    'Client.SetName': {
        'name': 'test name'
    },
    'Server.GetRPCVersion': {
        'major': 2,
        'minor': 0,
        'patch': 0
    },
    'Client.SetName': {
        'name': 'new name'
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
    'Client.GetStatus': {
        'client': {
            'config': {}
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

def get_mock_coro(return_value):
    @asyncio.coroutine
    def mock_coro(*args, **kwargs):
        return return_value
    return mock_coro()

class TestSnapserver(unittest.TestCase):

    #@mock.patch.object(Snapserver, '_transact', return_value=return_values['Server.GetStatus'])
    def setUp(self):
        self.loop = asyncio.get_event_loop()
        #self.server = get_server(self.loop)
        #with mock.patch.object(Snapserver, '_transact', return_value=get_mock_coro(return_values['Server.GetStatus'])):
        coro = create_server(self.loop, '0.0.0.0')
        self.server = self.loop.run_until_complete(coro)

    def tearDown(self):
        pass
        #self.loop.close()

    def test_init(self):
        self.assertEqual(self.server.version, 0.11)
        self.assertEqual(len(self.server.clients), 1)
        self.assertEqual(len(self.server.groups), 1)
        self.assertEqual(len(self.server.streams), 1)
        self.assertEqual(self.server.group('test').identifier, 'test')
        self.assertEqual(self.server.stream('stream').identifier, 'stream')
        self.assertEqual(self.server.client('test').identifier, 'test')

    def test_status(self):
        print('hello')
        status = yield from self.server.status()
        print('my status', status)
        self.assertEqual(status.get('server').get('version'), 0.11)

    def test_rpc_version(self):
        version = yield from self.server.rpc_version()
        self.assertEqual(version, {'major': 2, 'minor': 0, 'patch': 0})

    def test_client_name(self):
        name = yield from self.server.client_name('test', 'test name')
        self.assertEqual(name, 'test name')

    def test_client_set_invalid(self):
        yield from self.server.client_name('efgh', 'test name')
        # TODO: add assert

    @mock.patch.object(Snapserver, '_transact', return_value=return_values['Server.DeleteClient'])
    def test_delete_client(self, transact):
        yield from self.server.delete_client('test')
        self.assertEqual(len(self.server.clients), 0)

    def test_client_name(self):
        result = yield from self.server.client_name('test', 'new name')
        self.assertEqual(result, 'new name')

    def test_client_latency(self):
        result = yield from self.server.client_latency('test', 50)
        print("LASTENCY", result)
        self.assertEqual(result, 50)

    def test_client_volume(self):
        vol = {'percent': 50, 'muted': True}
        result = yield from self.server.client_volume('test', vol)
        self.assertEqual(result, vol)

    def test_client_status(self):
        result = yield from self.server.client_status('test')
        self.assertEqual(result, {'config': {}})

    def test_group_status(self):
        result = yield from self.server.group_status('test')
        self.assertEqual(result, {'clients': []})

    def test_group_mute(self):
        result = yield from self.server.group_mute('test', True)
        self.assertEqual(result, True)

    def test_group_stream(self):
        result = yield from self.server.group_stream('test', 'stream')
        self.assertEqual(result, 'stream')

    def test_group_clients(self):
        result = yield from self.server.group_clients('test', ['test'])
        self.assertEqual(result, ['test'])

    def test_synchronize(self):
        status = yield from self.server.status()
        status['server']['version'] = '0.12'
        self.server.synchronize(status)
        self.assertEqual(self.server.version, '0.12')
        print(self.server.version)

    """
    def test_invalid_event(self):
        with self.assertRaises(ValueError):
            self.server._on_event({'method': 'bad'})
    """

    def test_on_server_update(self):
        status = yield from self.server.status()
        status['server']['version'] = '0.12'
        yield from self.server._on_server_update(status)
        self.assertEqual(self.server.version, '0.12')

    def test_on_group_mute(self):
        data = {
            'id': 'test',
            'mute': True
        }
        yield from self.server._on_group_mute(data)
        self.assertEqual(self.server.group('test').muted, True)

    def test_on_group_stream_changed(self):
        data = {
            'id': 'test',
            'stream_id': 'other'
        }
        yield from self.server._on_group_stream_changed(data)
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
        yield from self.server._on_client_connect(data)
        self.assertEqual(self.server.client('new').connected, True)

    def test_on_client_disconnect(self):
        data = {
            'id': 'test'
        }
        yield from self.server._on_client_disconnect(data)
        self.assertEqual(self.server.client('test').connected, False)

    def test_on_client_volume_changed(self):
        data = {
            'id': 'test',
            'volume': {
                'percent': 50,
                'muted': True
            }
        }
        yield from self.server._on_client_volume_changed(data)
        self.assertEqual(self.server.client('test').volume, 50)
        self.assertEqual(self.server.client('test').muted, True)

    def test_on_client_name_changed(self):
        data = {
            'id': 'test',
            'name': 'new'
        }
        yield from self.server._on_client_name_changed(data)
        self.assertEqual(self.server.client('test').name, 'new')

    def test_on_client_latency_changed(self):
        data = {
            'id': 'test',
            'latency': 50
        }
        yield from self.server._on_client_latency_changed(data)
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
        print(self.server.stream('stream').status, 'idle')
        self.assertEqual(self.server.stream('stream').status, 'idle')
