"""Snapcast server."""

import asyncio
import logging
from snapcast.control.protocol import SnapcastProtocol
from snapcast.control.client import Snapclient
from snapcast.control.group import Snapgroup
from snapcast.control.stream import Snapstream


_LOGGER = logging.getLogger(__name__)

CONTROL_PORT = 1705

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


class Snapserver(object):
    """Represents a snapserver."""

    # pylint: disable=too-many-instance-attributes
    def __init__(self, loop, host, port=CONTROL_PORT):
        """Initialize."""
        self._loop = loop
        self._port = port
        self._clients = {}
        self._streams = {}
        self._groups = {}
        self._host = host
        self._version = None
        self._protocol = None
        self._callbacks = {
            CLIENT_ONCONNECT: self._on_client_connect,
            CLIENT_ONDISCONNECT: self._on_client_disconnect,
            CLIENT_ONVOLUMECHANGED: self._on_client_volume_changed,
            CLIENT_ONNAMECHANGED: self._on_client_name_changed,
            CLIENT_ONLATENCYCHANGED: self._on_client_latency_changed,
            GROUP_ONMUTE: self._on_group_mute,
            GROUP_ONSTREAMCHANGED: self._on_group_stream_changed,
            STREAM_ONUPDATE: self._on_stream_update,
            SERVER_ONUPDATE: self._on_server_update
        }

    def start(self):
        """Initiate server connection."""
        _, self._protocol = yield from self._loop.create_connection(
            lambda: SnapcastProtocol(self._callbacks), self._host, self._port)
        _LOGGER.info('connected to snapserver on %s:%s', self._host, self._port)
        status = yield from self.status()
        self.synchronize(status)

    @asyncio.coroutine
    def _transact(self, method, params=None):
        """Wrap requests."""
        result = yield from self._protocol.request(method, params)
        return result

    @property
    def version(self):
        """Version."""
        return self._version

    def status(self):
        """System status."""
        result = yield from self._transact(SERVER_GETSTATUS)
        return result

    def rpc_version(self):
        """RPC version."""
        return self._transact(SERVER_GETRPCVERSION)

    def delete_client(self, identifier):
        """Delete client."""
        params = {'id': identifier}
        response = yield from self._transact(SERVER_DELETECLIENT, params)
        self.synchronize(response)

    def client_name(self, identifier, name):
        """Set client name."""
        return self._request(CLIENT_SETNAME, identifier, 'name', name)

    def client_latency(self, identifier, latency):
        """Set client latency."""
        return self._request(CLIENT_SETLATENCY, identifier, 'latency', latency)

    def client_volume(self, identifier, volume):
        """Set client volume."""
        return self._request(CLIENT_SETVOLUME, identifier, 'volume', volume)

    def client_status(self, identifier):
        """Get client status."""
        return self._request(CLIENT_GETSTATUS, identifier, 'client')

    def group_status(self, identifier):
        """Get group status."""
        return self._request(GROUP_GETSTATUS, identifier, 'group')

    def group_mute(self, identifier, status):
        """Set group mute."""
        return self._request(GROUP_SETMUTE, identifier, 'mute', status)

    def group_stream(self, identifier, stream_id):
        """Set group stream."""
        return self._request(GROUP_SETSTREAM, identifier, 'stream_id', stream_id)

    def group_clients(self, identifier, clients):
        """Set group clients."""
        return self._request(GROUP_SETCLIENTS, identifier, 'clients', clients)

    def group(self, group_identifier):
        """Get a group."""
        return self._groups[group_identifier]

    def stream(self, stream_identifier):
        """Get a stream."""
        return self._streams[stream_identifier]

    def client(self, client_identifier):
        """Get a client."""
        return self._clients[client_identifier]

    @property
    def groups(self):
        """Get groups."""
        return list(self._groups.values())

    @property
    def clients(self):
        """Get clients."""
        return list(self._clients.values())

    @property
    def streams(self):
        """Get streams."""
        return list(self._streams.values())

    def synchronize(self, status):
        """Synchronize snapserver."""
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
        """Perform request with identifier."""
        params = {'id': identifier}
        if key is not None and value is not None:
            params[key] = value
        result = yield from self._transact(method, params)
        return result.get(key)

    def _on_server_update(self, data):
        """Handle server update."""
        self.synchronize(data)

    def _on_group_mute(self, data):
        """Handle group mute."""
        self._groups.get(data.get('id')).update_mute(data)

    def _on_group_stream_changed(self, data):
        """Handle group stream change."""
        self._groups.get(data.get('id')).update_stream(data)

    def _on_client_connect(self, data):
        """Handle client connect."""
        if data.get('id') in self._clients:
            self._clients[data.get('id')].update_connected(True)
        else:
            self._clients[data.get('id')] = Snapclient(self, data.get('client'))
        _LOGGER.info('client %s connected', self._clients[data.get('id')].friendly_name)

    def _on_client_disconnect(self, data):
        """Handle client disconnect."""
        self._clients[data.get('id')].update_connected(False)
        _LOGGER.info('client %s disconnected', self._clients[data.get('id')].friendly_name)

    def _on_client_volume_changed(self, data):
        """Handle client volume change."""
        self._clients.get(data.get('id')).update_volume(data)

    def _on_client_name_changed(self, data):
        """Handle client name changed."""
        self._clients.get(data.get('id')).update_name(data)

    def _on_client_latency_changed(self, data):
        """Handle client latency changed."""
        self._clients.get(data.get('id')).update_latency(data)

    def _on_stream_update(self, data):
        """Handle stream update."""
        self._streams[data.get('id')].update(data.get('stream'))
        _LOGGER.info('stream %s updated', self._streams[data.get('id')].friendly_name)
        for group in self._groups.values():
            if group.stream == data.get('id'):
                group.callback()

    def __repr__(self):
        """String representation."""
        return 'Snapserver {} ({})'.format(self.version, self._host)
