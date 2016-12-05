""" Snapcast control.

Compatible with version 0.8.0.
"""

import datetime
import json
import queue
import random
import threading
import telnetlib
import time


CONTROL_PORT = 1705
_NEWLINE = b'\r\n'
_ENCODING = 'utf-8'
_READ_TIMEOUT = 0.5
_RESP_TIMEOUT = 2.0  # In python2.7 response time is longer

SERVER_GETSTATUS = 'Server.GetStatus'
SERVER_DELETECLIENT = 'Server.DeleteClient'
CLIENT_SETNAME = 'Client.SetName'
CLIENT_SETLATENCY = 'Client.SetLatency'
CLIENT_SETMUTE = 'Client.SetMute'
CLIENT_SETSTREAM = 'Client.SetStream'
CLIENT_SETVOLUME = 'Client.SetVolume'
CLIENT_ONUPDATE = 'Client.OnUpdate'
CLIENT_ONDELETE = 'Client.OnDelete'
CLIENT_ONCONNECT = 'Client.OnConnect'
CLIENT_ONDISCONNECT = 'Client.OnDisconnect'
STREAM_ONUPDATE = 'Stream.OnUpdate'

_EVENTS = [CLIENT_ONUPDATE, CLIENT_ONCONNECT, CLIENT_ONDISCONNECT,
           CLIENT_ONDELETE, STREAM_ONUPDATE]
_METHODS = [SERVER_GETSTATUS, SERVER_DELETECLIENT, CLIENT_SETNAME,
            CLIENT_SETLATENCY, CLIENT_SETSTREAM, CLIENT_SETMUTE,
            CLIENT_SETVOLUME]


class Snapclient:
    """ Represents a snapclient. """
    def __init__(self, server, data):
        self._server = server
        self._mac = data.get('host').get('mac')
        self._last_seen = None
        self.update(data)

    @property
    def mac(self):
        """ MAC. """
        return self._mac

    @property
    def identifier(self):
        """ Readable identifier. """
        if len(self._client.get('config').get('name')):
            return self._client.get('config').get('name')
        return self._client.get('IP')

    @property
    def version(self):
        """ Version. """
        return self._client.get('snapclient').get('version')

    @property
    def connected(self):
        """ Connected or not. """
        return self._client.get('connected')

    @property
    def name(self):
        """ Name. """
        return self._client.get('config').get('name')

    @name.setter
    def name(self, name):
        """ Set a client name. """
        if not name:
            name = ''
        self._client['config']['name'] = \
            self._server.client_name(self._mac, name)

    @property
    def latency(self):
        """ Latency. """
        return self._client.get('config').get('latency')

    @latency.setter
    def latency(self, latency):
        """ Set client latency. """
        self._client['config']['latency'] = \
            self._server.client_latency(self._mac, latency)

    @property
    def muted(self):
        """ Muted or not. """
        return self._client.get('config').get('volume').get('muted')

    @muted.setter
    def muted(self, status):
        """ Set client mute status. """
        self._client['config']['volume']['muted'] = \
            self._server.client_muted(self._mac, status)

    @property
    def stream(self):
        """ Stream. """
        return self._server.stream(self._client.get('config').get('stream'))

    @stream.setter
    def stream(self, path):
        """ Set client stream path. """
        if path not in self.available_streams():
            raise ValueError('Invalid stream ID')
        self._client['config']['stream'] = self._server.client_stream(
            self._mac, path)

    def available_streams(self):
        """ List of available stream IDs. """
        return [stream.identifier for stream in self._server.streams]

    def streams_by_name(self):
        """ Get available stream objects by name. """
        return {stream.name: stream for stream in self._server.streams}

    @property
    def volume(self):
        """ Volume percent. """
        return self._client.get('config').get('volume').get('percent')

    @volume.setter
    def volume(self, percent):
        """ Set client volume percent. """
        if percent not in range(0, 101):
            raise ValueError('Volume percent out of range')
        self._client['config']['volume']['percent'] = \
            self._server.client_volume(self._mac, percent)

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
    def __init__(self, host, port=CONTROL_PORT):
        self._conn = telnetlib.Telnet(host, port)
        self._host = host
        self._clients = {}
        self._streams = {}
        self._buffer = {}
        self._queue = queue.Queue()
        tcp = threading.Thread(target=self._read)
        tcp.setDaemon(True) #python2.7
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
    def streams(self):
        """ Streams. """
        return list(self._streams.values())

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

    def client_stream(self, mac, stream):
        """ Set client stream. """
        return self._client(CLIENT_SETSTREAM, mac, 'id', stream)

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
            if client.get('host').get('mac') == mac:
                return client
        raise ValueError('No client at given mac')

    def stream(self, stream_id):
        """ Get a particular stream. """
        if stream_id in self._streams:
            return self._streams[stream_id]
        else:
            raise ValueError("Stream {} doesn't exist".format(stream_id))

    def synchronize(self):
        """ Synchronize snapserver. """
        status = self.status()
        self._version = status.get('server').get('version')
        self._clients = {}
        for client in status.get('clients'):
            self._clients[client.get('host').get('mac')] = \
                Snapclient(self, client)
        self._streams = {}
        for stream in status.get('streams'):
            self._streams[stream.get('id')] = Snapstream(stream)

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
            raw = self._conn.read_until(_NEWLINE, _READ_TIMEOUT)
            buf += raw
            try:
                response = json.loads(buf.decode(_ENCODING))
            except ValueError:
                continue
            if 'id' in response:
                if 'error' in response:
                    raise ValueError(response.get('error').get('message'))
                self._buffer[response.get('id')] = response.get('result')
            elif 'method' in response:
                self._on_event(response)
            else:
                raise ValueError(response)
            buf = b''

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
            elif event == STREAM_ONUPDATE:
                self._on_stream_update(data)
        else:
            raise ValueError('Unsupported event: {}', response.get('method'))

    def _on_update(self, data):
        """ Handle update event. """
        mac = data.get('host').get('mac')
        if mac in self._clients:
            self._clients.get(mac).update(data)
        else:
            raise ValueError('Updating unknown client')

    def _on_delete(self, data):
        """ Handle delete event. """
        mac = data.get('host').get('mac')
        if mac in self._clients:
            del self._clients[mac]
        else:
            raise ValueError('Deleting unknown client')

    def _on_connect(self, data):
        self._on_update(data)

    def _on_disconnect(self, data):
        self._on_update(data)

    def _on_stream_update(self, data):
        """ Handle stream update event. """
        stream_id = data.get('id')
        if stream_id in self._streams:
            self._streams.get(stream_id).update(data)

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
        end = time.time() + _RESP_TIMEOUT
        while time.time() < end:
            if uid in self._buffer.keys():
                return self._buffer.get(uid)
        raise Exception('No response received')

    def __repr__(self):
        """ String representation. """
        return 'Snapserver {} ({})'.format(self.version, self._host)


class Snapstream:
    """ Represents a snapcast stream. """
    def __init__(self, data):
        self.update(data)

    @property
    def identifier(self):
        """ Get stream id. """
        return self._stream.get('id')

    @property
    def status(self):
        """ Get stream status. """
        return self._stream.get('status')

    @property
    def name(self):
        """ Get stream name. """
        return self._stream.get('uri').get('query').get('name')

    def update(self, data):
        """ Update stream. """
        self._stream = data

    def __repr__(self):
        """ String representation. """
        return 'Snapstream ({})'.format(self.name)
