import json
import queue
import telnetlib


class MockTelnet(object):
    encoding = 'utf-8'
    results = {
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
            'patch': 0
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

    def __init__(self, host, port):
        self._queue = queue.Queue()

    def write(self, data):
        self._queue.put(json.loads(data.decode(MockTelnet.encoding)))

    def read_until(self, b, timeout):
        try:
            resp = self._queue.get(timeout=timeout)
        except queue.Empty:
            return ''.encode(MockTelnet.encoding)
        return '{}{}'.format(json.dumps({
            'jsonrpc': '2.0',
            'id': resp['id'],
            'result': MockTelnet.results.get(resp['method'])
        }),'\r\n').encode(MockTelnet.encoding)


telnetlib.Telnet = MockTelnet
