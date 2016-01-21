""" Snapcast control. """

import datetime
import json
import queue
import random
import threading
import telnetlib


CONTROL_PORT = 1705
_NEWLINE = b'\r\n'
_ENCODING = 'utf-8'
_TIMEOUT = 0.5

SERVER_GETSTATUS = 'Server.GetStatus'
SERVER_DELETECLIENT = 'Server.DeleteClient'
CLIENT_SETNAME = 'Client.SetName'
CLIENT_SETLATENCY = 'Client.SetLatency'
CLIENT_SETMUTE = 'Client.SetMute'
CLIENT_SETVOLUME = 'Client.SetVolume'
CLIENT_ONUPDATE = 'Client.OnUpdate'
CLIENT_ONDELETE = 'Client.OnDelete'
CLIENT_ONCONNECT = 'Client.OnConnect'
CLIENT_ONDISCONNECT = 'Client.OnDisconnect'

_EVENTS = [CLIENT_ONUPDATE, CLIENT_ONCONNECT, CLIENT_ONDISCONNECT,
           CLIENT_ONDELETE]
_METHODS = [SERVER_GETSTATUS, SERVER_DELETECLIENT, CLIENT_SETNAME,
            CLIENT_SETLATENCY, CLIENT_SETMUTE, CLIENT_SETVOLUME]


class Snapclient:
    """ Represents a snapclient. """
    def __init__(self, server, data):
        self._server = server
        self._mac = data.get('MAC')
        self._last_seen = None
        self.update(data)

    @property
    def mac(self):
        """ MAC. """
        return self._mac

    @property
    def identifier(self):
        """ Readable identifier. """
        if len(self._client.get('name')):
            return self._client.get('name')
        return self._client.get('IP')

    @property
    def version(self):
        """ Version. """
        return self._client.get('version')

    @property
    def connected(self):
        """ Connected or not. """
        return self._client.get('version')

    @property
    def name(self):
        """ Name. """
        return self._client.get('name')

    @name.setter
    def name(self, name):
        """ Set a client name. """
        if not name:
            name = ''
        self._client['name'] = self._server.client_name(self._mac, name)

    @property
    def latency(self):
        """ Latency. """
        return self._client.get('latency')

    @latency.setter
    def latency(self, latency):
        """ Set client latency. """
        self._client['latency'] = self._server.client_latency(self._mac,
                                                              latency)

    @property
    def muted(self):
        """ Muted or not. """
        return self._client.get('volume').get('muted')

    @muted.setter
    def muted(self, status):
        """ Set client mute status. """
        self._client['volume']['muted'] = self._server.client_muted(self._mac,
                                                                    status)

    @property
    def volume(self):
        """ Volume percent. """
        return self._client.get('volume').get('percent')

    @volume.setter
    def volume(self, percent):
        """ Set client volume percent. """
        if percent not in range(0, 101):
            raise ValueError('Volume percent out of range')
        self._client['volume']['percent'] = self._server.client_volume(
            self._mac,
            percent)

    def update(self, data):
        """ Update client with new state. """
        self._client = data
        milliseconds = ((self._client.get('lastSeen').get('sec') * 1000) +
                        self._client.get('lastSeen').get('usec'))
        self._last_seen = datetime.datetime.fromtimestamp(milliseconds // 1000)

    def __repr__(self):
        """ String representation. """
        return 'Snapclient {} ({}, {})'.format(self.version, self.identifier,
                                               self._mac)


class Snapserver:
    """ Represents a snapserver. """
    def __init__(self, host, port):
        self._conn = telnetlib.Telnet(host, port)
        self._host = host
        self._clients = {}
        self._buffer = {}
        self._queue = queue.Queue()
        tcp = threading.Thread(target=self._read, daemon=True)
        tcp.start()
        self.synchronize()

    def delete(self, client):
        """ Delete a client.

        Note that only other clients will receive
        the ON_DELETE event.
        """
        mac = self._client(SERVER_DELETECLIENT, client.mac)
        del self._clients[mac]

    @property
    def clients(self):
        """ Clients. """
        return list(self._clients.values())

    @property
    def version(self):
        """ Version. """
        return self._version

    def status(self):
        """ System status. """
        return self._transact(SERVER_GETSTATUS)

    def client_name(self, mac, name):
        """ Set client name. """
        return self._client(CLIENT_SETNAME, mac, 'name', name)

    def client_latency(self, mac, latency):
        """ Set client latency. """
        return self._client(CLIENT_SETLATENCY, mac, 'latency', latency)

    def client_muted(self, mac, muted):
        """ Set client mute status. """
        return self._client(CLIENT_SETMUTE, mac, 'mute', muted)

    def client_volume(self, mac, volume):
        """ Set client volume. """
        return self._client(CLIENT_SETVOLUME, mac, 'volume', volume)

    def client_status(self, mac):
        """ Client status.

        'System.GetStatus' with a 'client' parameter
        should probably just return the client record,
        but instead we get a full system status, so we
        have to extract just the relevant client record.
        """
        for client in self._client(SERVER_GETSTATUS, mac)['clients']:
            if client.get('MAC') == mac:
                return client
        raise ValueError('No client at given mac')

    def synchronize(self):
        """ Synchronize snapserver. """
        status = self.status()
        self._version = status.get('server').get('version')
        self._clients = {}
        for client in status.get('clients'):
            self._clients[client.get('MAC')] = Snapclient(self, client)

    def _client(self, method, mac, key=None, value=None):
        """ Perform client transact. """
        params = {'client': mac}
        if key is not None and value is not None:
            params[key] = value
        return self._transact(method, params)

    def _read(self):
        """ Read and write data.

        This method runs in a thread. It checks a queue
        for outgoing messages, and writes to a buffer for
        incoming response messages. Events are acted upon
        immediately.

        If a partial message is received, buffer until it
        is valid.
        """
        buf = b''
        while True:
            if not self._queue.empty():
                message = self._queue.get()
                self._conn.write(json.dumps(message)
                                 .encode(_ENCODING) + _NEWLINE)
            raw = self._conn.read_until(_NEWLINE, _TIMEOUT)
            buf += raw
            try:
                response = json.loads(buf.decode(_ENCODING))
                if 'id' in response:
                    self._buffer[response.get('id')] = response.get('result')
                elif 'method' in response:
                    self._on_event(response)
                else:
                    raise ValueError(response)
                buf = b''
            except ValueError:
                pass

    def _on_event(self, response):
        """ Handle incoming events. """
        if response.get('method') in _EVENTS:
            event = response.get('method')
            data = response.get('params').get('data')
            if event == CLIENT_ONUPDATE:
                self._on_update(data)
            elif event == CLIENT_ONDELETE:
                self._on_delete(data)
            elif event == CLIENT_ONCONNECT:
                self._on_connect(data)
            elif event == CLIENT_ONDISCONNECT:
                self._on_disconnect(data)
        else:
            raise ValueError('Unsupported event')

    def _on_update(self, data):
        """ Handle update event. """
        if data.get('MAC') in self._clients:
            self._clients.get(data.get('MAC')).update(data)
        else:
            raise ValueError('Updating unknown client')

    def _on_delete(self, data):
        """ Handle delete event. """
        if data.get('MAC') in self._clients:
            del self._clients[data.get('MAC')]
        else:
            raise ValueError('Deleting unknown client')

    def _on_connect(self, data):
        self._on_update(data)

    def _on_disconnect(self, data):
        self._on_update(data)

    def _transact(self, method, params=None):
        """ Transact via JSON RPC TCP. """
        if method not in _METHODS:
            raise ValueError('Invalid JSON RPC method')
        uid = random.randint(1, 1000)
        message = {
            'jsonrpc': '2.0',
            'method': method,
            'id': uid
        }
        if params:
            message['params'] = params
        self._queue.put(message)
        while True:
            if uid in self._buffer.keys():
                return self._buffer.get(uid)

    def __repr__(self):
        """ String representation. """
        return 'Snapserver {} ({})'.format(self.version, self._host)
