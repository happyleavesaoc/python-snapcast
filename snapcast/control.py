""" Snapcast control.

Compatible with version 0.11.0.
"""

import datetime
import json
import queue
import logging
import random
import threading
import telnetlib
import time


_LOGGER = logging.getLogger(__name__)

CONTROL_PORT = 1705
_NEWLINE = b'\r\n'
_ENCODING = 'utf-8'
_READ_TIMEOUT = 0.5
_RESP_TIMEOUT = 4.0  # In python2.7 response time is longer

SERVER_GETSTATUS = 'Server.GetStatus'
SERVER_GETRPCVERSION = 'Server.GetRPCVersion'
SERVER_DELETECLIENT = 'Server.DeleteClient'
SERVER_ONUPDATE = 'Server.OnUpdate'

CLIENT_GETSTATUS = 'Client.GetStatus'
CLIENT_SETNAME = 'Client.SetName'
CLIENT_SETLATENCY = 'Client.SetLatency'
CLIENT_SETSTREAM = 'Client.SetStream'
CLIENT_SETVOLUME = 'Client.SetVolume'
CLIENT_ONCONNECT = 'Client.OnConnect'
CLIENT_ONDISCONNECT = 'Client.OnDisconnect'
CLIENT_ONVOLUMECHANGED = 'Client.OnVolumeChanged'
CLIENT_ONLATENCYCHANGED = 'Client.OnLatencyChanged'
CLIENT_ONNAMECHANGED = 'Client.OnNameChanged'

GROUP_GETSTATUS = 'Group.GetStatus'
GROUP_SETMUTE = 'Group.SetMute'
GROUP_SETSTREAM = 'Group.SetStream'
GROUP_SETCLIENTS = 'Group.SetClients'
GROUP_ONMUTE = 'Group.OnMute'
GROUP_ONSTREAMCHANGED = 'Group.OnStreamChanged'

STREAM_ONUPDATE = 'Stream.OnUpdate'

_EVENTS = [SERVER_ONUPDATE, CLIENT_ONVOLUMECHANGED, CLIENT_ONLATENCYCHANGED,
           CLIENT_ONNAMECHANGED, CLIENT_ONCONNECT, CLIENT_ONDISCONNECT,
           GROUP_ONMUTE, GROUP_ONSTREAMCHANGED, STREAM_ONUPDATE]
_METHODS = [SERVER_GETSTATUS, SERVER_GETRPCVERSION, SERVER_DELETECLIENT,
            SERVER_DELETECLIENT, CLIENT_GETSTATUS, CLIENT_SETNAME,
            CLIENT_SETLATENCY, CLIENT_SETSTREAM, CLIENT_SETVOLUME,
            GROUP_GETSTATUS, GROUP_SETMUTE, GROUP_SETSTREAM, GROUP_SETCLIENTS]


class Snapclient(object):
    """ Represents a snapclient. """
    def __init__(self, server, data):
        self._server = server
        self._last_seen = None
        self._client = data

    @property
    def identifier(self):
        """ Get identifier. """
        return self._client.get('id')

    @property
    def group(self):
        """ Get group. """
        for group in self._server._groups.values():
            if self.identifier in group.clients:
                return group

    @property
    def friendly_name(self):
        """ Get friendly name. """
        if len(self._client.get('config').get('name')):
            return self._client.get('config').get('name')
        return self._client.get('host').get('name')

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
            self._server.client_name(self.identifier, name)

    @property
    def latency(self):
        """ Latency. """
        return self._client.get('config').get('latency')

    @latency.setter
    def latency(self, latency):
        """ Set client latency. """
        self._client['config']['latency'] = \
            self._server.client_latency(self.identifier, latency)

    @property
    def muted(self):
        """ Muted or not. """
        return self._client.get('config').get('volume').get('muted')

    @muted.setter
    def muted(self, status):
        """ Set client mute status. """
        new_volume = self._client['config']['volume']
        new_volume['muted'] = status
        self._client['config']['volume']['muted'] = status
        print(self._server.client_volume(self.identifier, new_volume))
        _LOGGER.info('set muted to %s on %s', status, self.friendly_name)

    @property
    def volume(self):
        """ Volume percent. """
        return self._client.get('config').get('volume').get('percent')

    @volume.setter
    def volume(self, percent):
        """ Set client volume percent. """
        if percent not in range(0, 101):
            raise ValueError('Volume percent out of range')
        new_volume = self._client['config']['volume']
        new_volume['percent'] = percent
        self._client['config']['volume']['percent'] = percent
        print(self._server.client_volume(self.identifier, new_volume))
        _LOGGER.info('set volume to %s on %s', percent, self.friendly_name)

    def update_volume(self, data):
        """ Update volume. """
        self._client['config']['volume'] = data['volume']
        _LOGGER.info('updated volume on %s', self.friendly_name)
        self._callback(data)

    def update_name(self, data):
        """ Update name. """
        self._client['config']['name'] = data['name']
        _LOGGER.info('updated name on %s', self.friendly_name)
        self._callback(data)

    def update_latency(self, data):
        """ Update latency. """
        self._client['config']['latency'] = data['latency']
        _LOGGER.info('updated latency on %s', self.friendly_name)
        self._callback(data)

    def update_connected(self, status):
        """ Update connected. """
        self._client['connected'] = status
        _LOGGER.info('updated connected status to %s on %s', status, self.friendly_name)
        self._callback(status)

    def _callback(self, data):
        if self._callback_func and callable(self._callback_func):
            print('CALLBACK GO')
            self._callback_func()

    def set_callback(self, func):
        self._callback_func = func

    def __repr__(self):
        """ String representation. """
        return 'Snapclient {} ({}, {})'.format(self.version, self.friendly_name,
                                               self.identifier)


class Snapserver(object):
    """ Represents a snapserver. """
    def __init__(self, host, port=CONTROL_PORT):
        self._conn = telnetlib.Telnet(host, port)
        _LOGGER.info('connected to snapserver on %s:%s', host, port)
        self._host = host
        self._clients = {}
        self._streams = {}
        self._groups = {}
        self._buffer = {}
        self._queue = queue.Queue()
        tcp = threading.Thread(target=self._read)
        tcp.setDaemon(True) #python2.7
        tcp.start()
        self.synchronize(self.status())

    @property
    def clients(self):
        """ Clients. """
        return list(self._clients.values())

    @property
    def streams(self):
        """ Streams. """
        return list(self._streams.values())

    @property
    def groups(self):
        """ Groups. """
        return list(self._groups.values())

    @property
    def version(self):
        """ Version. """
        return self._version

    def status(self):
        """ System status. """
        return self._transact(SERVER_GETSTATUS)

    def rpc_version(self):
        """ RPC version. """
        return self._transact(SERVER_GETRPCVERSION)

    def delete_client(self, identifier):
        """ Delete client. """
        params = {'id': identifier}
        response = self._transact(SERVER_DELETECLIENT, params)
        self.synchronize(response)

    def client_name(self, identifier, name):
        """ Set client name. """
        return self._request(CLIENT_SETNAME, identifier, 'name', name)

    def client_latency(self, identifier, latency):
        """ Set client latency. """
        return self._request(CLIENT_SETLATENCY, identifier, 'latency', latency)

    def client_volume(self, identifier, volume):
        """ Set client volume. """
        return self._request(CLIENT_SETVOLUME, identifier, 'volume', volume)

    def client_status(self, identifier):
        """ Get client status. """
        return self._request(CLIENT_GETSTATUS, identifier, 'client')

    def group_status(self, identifier):
        """ Get group status. """
        return self._request(GROUP_GETSTATUS, identifier, 'group')

    def group_mute(self, identifier, status):
        """ Set group mute. """
        return self._request(GROUP_SETMUTE, identifier, 'mute', status)

    def group_stream(self, identifier, stream_id):
        """ Set group stream. """
        return self._request(GROUP_SETSTREAM, identifier, 'stream_id', stream_id)

    def group_clients(self, identifier, clients):
        """ Set group clients. """
        return self._request(GROUP_SETCLIENTS, identifier, 'clients', clients)

    def group(self, group_identifier):
        """ Get a group. """
        return self._groups[group_identifier]

    def stream(self, stream_identifier):
        """ Get a stream. """
        return self._streams[stream_identifier]

    def synchronize(self, status):
        """ Synchronize snapserver. """
        self._version = status.get('server').get('version')
        self._groups = {}
        self._clients = {}
        self._streams = {}
        for stream in status.get('server').get('streams'):
            self._streams[stream.get('id')] = Snapstream(stream)
            _LOGGER.debug('stream found: %s', self._streams[stream.get('id')])
        for group in status.get('server').get('groups'):
            self._groups[group.get('id')] = Snapgroup(self, group)
            _LOGGER.debug('group found: %s', self._groups[group.get('id')])
            for client in group.get('clients'):
                self._clients[client.get('id')] = Snapclient(self, client)
                _LOGGER.debug('client found: %s', self._clients[client.get('id')])

    def _request(self, method, identifier, key=None, value=None):
        """ Perform request with identifier. """
        params = {'id': identifier}
        if key is not None and value is not None:
            params[key] = value
        return self._transact(method, params).get(key)

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
            # Handle batch responses
            if isinstance(response, list):
                for resp in response:
                    self._process_response(resp)
            else:
                self._process_response(response)
            buf = b''

    def _process_response(self, response):
        """ Process a response. """
        if 'id' in response:
            if 'error' in response:
                raise ValueError('{}: {}'.format(response.get('error').get('message'), response.get('error').get('data')))
            self._buffer[response.get('id')] = response.get('result')
        elif 'method' in response:
            self._on_event(response)
        else:
            raise ValueError(response)

    def _on_event(self, response):
        """ Handle incoming events. """
        event = response.get('method')
        if event not in _EVENTS:
            raise ValueError('Unsupported event: {}', event)
            return
        _LOGGER.debug('received notification %s', event)
        data = response.get('params')
        if event == CLIENT_ONCONNECT:
            self._on_client_connect(data)
        elif event == CLIENT_ONDISCONNECT:
            self._on_client_disconnect(data)
        elif event == CLIENT_ONVOLUMECHANGED:
            self._on_client_volume_changed(data)
        elif event == CLIENT_ONNAMECHANGED:
            self._on_client_name_changed(data)
        elif event == CLIENT_ONLATENCYCHANGED:
            self._on_client_latency_changed(data)
        elif event == GROUP_ONMUTE:
            self._on_group_mute(data)
        elif event == GROUP_ONSTREAMCHANGED:
            self._on_group_stream_changed(data)
        elif event == STREAM_ONUPDATE:
            self._on_stream_update(data)
        elif event == SERVER_ONUPDATE:
            self._on_server_update(data)

    def _on_server_update(self, data):
        """ Handle server update. """
        self.synchronize(data)

    def _on_group_mute(self, data):
        """ Handle group mute. """
        self._groups.get(data.get('id')).update_mute(data)

    def _on_group_stream_changed(self, data):
        """ Handle group stream change. """
        self._groups.get(data.get('id')).update_stream(data)

    def _on_client_connect(self, data):
        """ Handle client connect. """
        if data.get('id') in self._clients:
            self._clients[data.get('id')].update_connected(True)
        else:
            self._clients[data.get('id')] = Snapclient(self, data.get('client'))
        _LOGGER.info('client %s connected', self._clients[data.get('id')].friendly_name)

    def _on_client_disconnect(self, data):
        """ Handle client disconnect. """
        self._clients[data.get('id')].update_connected(False)
        _LOGGER.info('client %s disconnected', self._clients[data.get('id')].friendly_name)

    def _on_client_volume_changed(self, data):
        """ Handle client volume change. """
        self._clients.get(data.get('id')).update_volume(data)

    def _on_client_name_changed(self, data):
        """ Handle client name changed. """
        self._clients.get(data.get('id')).update_name(data)

    def _on_client_latency_changed(self, data):
        """ Handle client latency changed. """
        self._clients.get(data.get('id')).update_latency(data)

    def _on_stream_update(self, data):
        """ Handle stream update. """
        self._streams[data.get('id')].update(data.get('stream'))
        _LOGGER.info('stream %s updated', self._streams[data.get('id')].friendly_name)
        for group in self._groups.values():
            if group.stream == data.get('id'):
                group._callback(True)

    def _transact(self, method, params=None):
        """ Transact via JSON RPC TCP. """
        if method not in _METHODS:
            raise ValueError('Invalid JSON RPC method')
        _LOGGER.debug('sending request %s', method)
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


class Snapstream(object):
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

    @property
    def friendly_name(self):
        """ Get friendly name. """
        return self.name if self.name != '' else self.identifier

    def update(self, data):
        """ Update stream. """
        self._stream = data

    def __repr__(self):
        """ String representation. """
        return 'Snapstream ({})'.format(self.name)


class Snapgroup(object):
    """ Represents a snapcast group. """
    def __init__(self, server, data):
        self._server = server
        self.update(data)

    def update(self, data):
        """ Update group. """
        self._group = data

    @property
    def identifier(self):
        """ Get group identifier. """
        return self._group.get('id')

    @property
    def name(self):
        """ Get group name. """
        return self._group.get('name')

    @property
    def stream(self):
        """ Get stream identifier. """
        return self._group.get('stream_id')

    @stream.setter
    def stream(self, stream_id):
        """ Set group stream. """
        self._group['stream_id'] = \
            self._server.group_stream(self.identifier, stream_id)
        _LOGGER.info('set stream to %s on %s', stream_id, self.friendly_name)

    @property
    def stream_status(self):
        """ Get stream status. """
        return self._server.stream(self.stream).status

    @property
    def muted(self):
        """ Get mute status. """
        return self._group.get('muted')

    @muted.setter
    def muted(self, status):
        """ Set group mute status. """
        self._group['muted'] = \
            self._server.group_mute(self.identifier, status)
        _LOGGER.info('set muted to %s on %s', status, self.friendly_name)

    @property
    def friendly_name(self):
        """ Get friendly name. """
        return self.name if self.name != '' else self.stream

    @property
    def clients(self):
        """ Get client identifiers. """
        return [client.get('id') for client in self._group.get('clients')]

    def add_client(self, client_identifier):
        """ Add a client. """
        if client_identifier in self.clients:
            _LOGGER.error('%s already in group %s', client_identifier, self.identifier)
            return
        new_clients = self.clients
        new_clients.append(client_identifier)
        self._server.group_clients(self.identifier, new_clients)
        _LOGGER.info('added %s to %s', client_identifier, self.identifier)
        self._server._clients[client_identifier]._callback(True)
        self._callback(True)

    def remove_client(self, client_identifier):
        """ Remove a client. """
        new_clients = self.clients
        new_clients.remove(client_identifier)
        self._server.group_clients(self.identifier, new_clients)
        _LOGGER.info('removed %s from %s', client_identifier, self.identifier)
        self._server._clients[client_identifier]._callback(True)
        self._callback(True)

    def streams_by_name(self):
        """ Get available stream objects by name. """
        return {stream.friendly_name: stream for stream in self._server.streams}

    def update_mute(self, data):
        """ Update mute. """
        self._group['muted'] = data['mute']
        self._callback(data)
        _LOGGER.info('updated mute on %s', self.friendly_name)

    def update_stream(self, data):
        """ Update stream. """
        self._group['stream_id'] = data['stream_id']
        self._callback(data)
        _LOGGER.info('updated stream to %s on %s', self.stream, self.friendly_name)

    def _callback(self, data):
        if self._callback_func and callable(self._callback_func):
            self._callback_func()

    def set_callback(self, func):
        self._callback_func = func

    def __repr__(self):
        """ String representation. """
        return 'Snapgroup ({}, {})'.format(self.friendly_name, self.identifier)
