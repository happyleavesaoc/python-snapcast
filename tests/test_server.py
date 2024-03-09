import asyncio
import copy
import unittest
from unittest import mock
from unittest.mock import AsyncMock, MagicMock

from snapcast.control.server import Snapserver
from snapcast.control import create_server


SERVER_STATUS = {
    'host': {
        'arch': 'x86_64',
        'ip': '',
        'mac': '',
        'name': 'T400',
        'os': 'Linux Mint 17.3 Rosa'
    },
    'snapserver': {
        'controlProtocolVersion': 1,
        'name': 'Snapserver',
        'protocolVersion': 1,
        'version': '0.26.0'
    }
}

return_values = {
    'Server.GetStatus': {
        'server': {
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
            'server': SERVER_STATUS,
            'streams': [
                {
                    'id': 'stream',
                    'status': 'playing',
                    'uri': {
                        'query': {
                            'name': 'stream'
                        }
                    },
                    'properties': {
                        'canControl': False,
                        'metadata': {
                            'title': 'Happy!',
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
            'server': SERVER_STATUS,  # DeleteClient calls synchronize
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
    },
    'Stream.SetMeta': {
        'foo': 'bar'
    },
    'Stream.SetProperty': 'ok',
    'Stream.AddStream': {
        'id': 'stream 2'
    },
    'Stream.RemoveStream': {
        'id': 'stream 2'
    },
}


def mock_transact(key):
    return AsyncMock(return_value=(return_values[key], None))


class TestSnapserver(unittest.TestCase):

    def _run(self, coro):
        return asyncio.run(coro)

    @mock.patch.object(Snapserver, 'start', new=AsyncMock())
    def setUp(self):
        self.loop = MagicMock()
        self.server = self._run(create_server(self.loop, 'abcd'))
        self.server.synchronize(return_values.get('Server.GetStatus'))

    @mock.patch.object(Snapserver, 'status', new=AsyncMock(
        return_value=(None, {"code": -1, "message": "failed"})))
    @mock.patch.object(Snapserver, '_do_connect', new=AsyncMock())
    @mock.patch.object(Snapserver, 'stop', new=mock.MagicMock())
    def test_start_fail(self):
        with self.assertRaises(OSError):
            self._run(self.server.start())

    @mock.patch.object(Snapserver, '_transact', new=mock_transact('Server.GetStatus'))
    @mock.patch.object(Snapserver, '_do_connect', new=AsyncMock())
    def test_start(self):
        self.server._version = None
        self._run(self.server.start())
        self.assertEqual(self.server.version, '0.26.0')

    def test_init(self):
        self.assertEqual(self.server.version, '0.26.0')
        self.assertEqual(len(self.server.clients), 1)
        self.assertEqual(len(self.server.groups), 1)
        self.assertEqual(len(self.server.streams), 1)
        self.assertEqual(self.server.group('test').identifier, 'test')
        self.assertEqual(self.server.stream('stream').identifier, 'stream')
        self.assertEqual(self.server.client('test').identifier, 'test')

    @mock.patch.object(Snapserver, '_transact', new=mock_transact('Server.GetStatus'))
    def test_status(self):
        status, _ = self._run(self.server.status())
        self.assertEqual(status['server']['server']['snapserver']['version'], '0.26.0')

    @mock.patch.object(Snapserver, '_transact', new=mock_transact('Server.GetRPCVersion'))
    def test_rpc_version(self):
        version, _ = self._run(self.server.rpc_version())
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

    @mock.patch.object(Snapserver, '_transact', new=mock_transact('Stream.SetMeta'))
    def test_stream_setmeta(self):
        result = self._run(self.server.stream_setmeta('stream', {'foo': 'bar'}))
        self.assertEqual(result, {'foo': 'bar'})

    @mock.patch.object(Snapserver, '_transact', new=mock_transact('Stream.SetProperty'))
    def test_stream_setproperty(self):
        result = self._run(self.server.stream_setproperty('stream', 'foo', 'bar'))
        self.assertEqual(result, 'ok')

    @mock.patch.object(Snapserver, '_transact', new=mock_transact('Stream.AddStream'))
    @mock.patch.object(Snapserver, 'synchronize', new=MagicMock())
    def test_stream_addstream(self):
        result = self._run(self.server.stream_add_stream('pipe:///tmp/test?name=stream 2'))
        self.assertDictEqual(result, {'id': 'stream 2'})

    @mock.patch.object(Snapserver, '_transact', new=mock_transact('Stream.RemoveStream'))
    @mock.patch.object(Snapserver, 'synchronize', new=MagicMock())
    def test_stream_removestream(self):
        result = self._run(self.server.stream_remove_stream('stream 2'))
        self.assertDictEqual(result, {'id': 'stream 2'})

    def test_synchronize(self):
        status = copy.deepcopy(return_values.get('Server.GetStatus'))
        status['server']['server']['snapserver']['version'] = '0.12'
        self.server.synchronize(status)
        self.assertEqual(self.server.version, '0.12')

    def test_on_server_connect(self):
        cb = mock.MagicMock()
        self.server.set_on_connect_callback(cb)
        self.server._on_server_connect()
        cb.assert_called_with()

    def test_on_server_disconnect(self):
        cb = mock.MagicMock()
        self.server.set_on_disconnect_callback(cb)
        e = Exception()
        self.server._on_server_disconnect(e)
        cb.assert_called_with(e)

    def test_on_server_update(self):
        cb = mock.MagicMock()
        self.server.set_on_update_callback(cb)
        status = copy.deepcopy(return_values.get('Server.GetStatus'))
        status['server']['server']['snapserver']['version'] = '0.12'
        self.server._on_server_update(status)
        self.assertEqual(self.server.version, '0.12')
        cb.assert_called_with()

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

    def test_on_meta_update(self):
        data = {
            'id': 'stream',
            'meta': {
                'TITLE': 'Happy!'
            }
        }
        self.server._on_stream_meta(data)
        self.assertDictEqual(self.server.stream('stream').meta, data['meta'])

    def test_on_properties_update(self):
        data = {
            'id': 'stream',
            'properties': {
                'canControl': True,
                'metadata': {
                    'title': 'Unhappy!',
                }
            }
        }
        self.server._on_stream_properties(data)
        self.assertDictEqual(self.server.stream('stream').properties, data['properties'])
