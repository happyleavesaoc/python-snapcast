"""Snapcast server."""

import asyncio
import logging
import websockets

from packaging import version
from snapcast.control.client import Snapclient
from snapcast.control.group import Snapgroup
from snapcast.control.protocol import SERVER_ONDISCONNECT, SnapcastProtocol
from snapcast.control.wsprotocol import SnapcastWebSocketProtocol
from snapcast.control.stream import Snapstream

_LOGGER = logging.getLogger(__name__)

CONTROL_PORT = 1705
WEBSOCKET_PORT = 1780

SERVER_GETSTATUS = 'Server.GetStatus'
SERVER_GETRPCVERSION = 'Server.GetRPCVersion'
SERVER_DELETECLIENT = 'Server.DeleteClient'
SERVER_ONUPDATE = 'Server.OnUpdate'

CLIENT_GETSTATUS = 'Client.GetStatus'
CLIENT_SETNAME = 'Client.SetName'
CLIENT_SETLATENCY = 'Client.SetLatency'
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
GROUP_SETNAME = 'Group.SetName'
GROUP_ONMUTE = 'Group.OnMute'
GROUP_ONSTREAMCHANGED = 'Group.OnStreamChanged'
GROUP_ONNAMECHANGED = 'Group.OnNameChanged'


STREAM_ONPROPERTIES = 'Stream.OnProperties'
STREAM_SETPROPERTY = 'Stream.SetProperty'
STREAM_CONTROL = 'Stream.Control'  # not yet implemented
STREAM_SETMETA = 'Stream.SetMeta'  # deprecated
STREAM_ONUPDATE = 'Stream.OnUpdate'
STREAM_ONMETA = 'Stream.OnMetadata'  # deprecated
STREAM_ADDSTREAM = 'Stream.AddStream'
STREAM_REMOVESTREAM = 'Stream.RemoveStream'

SERVER_RECONNECT_DELAY = 5

_EVENTS = [SERVER_ONUPDATE, CLIENT_ONVOLUMECHANGED, CLIENT_ONLATENCYCHANGED,
           CLIENT_ONNAMECHANGED, CLIENT_ONCONNECT, CLIENT_ONDISCONNECT,
           GROUP_ONMUTE, GROUP_ONSTREAMCHANGED, GROUP_ONNAMECHANGED, STREAM_ONUPDATE,
           STREAM_ONMETA, STREAM_ONPROPERTIES]
_METHODS = [SERVER_GETSTATUS, SERVER_GETRPCVERSION, SERVER_DELETECLIENT,
            SERVER_DELETECLIENT, CLIENT_GETSTATUS, CLIENT_SETNAME,
            CLIENT_SETLATENCY, CLIENT_SETVOLUME,
            GROUP_GETSTATUS, GROUP_SETMUTE, GROUP_SETSTREAM, GROUP_SETCLIENTS,
            GROUP_SETNAME, STREAM_SETMETA, STREAM_SETPROPERTY, STREAM_CONTROL,
            STREAM_ADDSTREAM, STREAM_REMOVESTREAM]

# server versions in which new methods were added
_VERSIONS = {
    GROUP_SETNAME: '0.16.0',
    STREAM_SETPROPERTY: '0.26.0',
    STREAM_ADDSTREAM: '0.16.0',
    STREAM_REMOVESTREAM: '0.16.0',
}


class ServerVersionError(NotImplementedError):
    """Server Version Error, not implemented."""

    pass


# pylint: disable=too-many-public-methods
class Snapserver():
    """Represents a snapserver."""

    # pylint: disable=too-many-instance-attributes,too-many-arguments
    def __init__(self, loop, host, port=CONTROL_PORT, reconnect=False, use_websockets=False):
        """Initialize."""
        self._loop = loop
        self._use_websockets = use_websockets
        self._port = port
        self._reconnect = reconnect
        self._is_stopped = True
        self._clients = {}
        self._streams = {}
        self._groups = {}
        self._host = host
        self._version = None
        self._protocol = None
        self._transport = None
        self._websocket = None
        self._callbacks = {
            CLIENT_ONCONNECT: self._on_client_connect,
            CLIENT_ONDISCONNECT: self._on_client_disconnect,
            CLIENT_ONVOLUMECHANGED: self._on_client_volume_changed,
            CLIENT_ONNAMECHANGED: self._on_client_name_changed,
            CLIENT_ONLATENCYCHANGED: self._on_client_latency_changed,
            GROUP_ONMUTE: self._on_group_mute,
            GROUP_ONSTREAMCHANGED: self._on_group_stream_changed,
            GROUP_ONNAMECHANGED: self._on_group_name_changed,
            STREAM_ONMETA: self._on_stream_meta,
            STREAM_ONPROPERTIES: self._on_stream_properties,
            STREAM_ONUPDATE: self._on_stream_update,
            SERVER_ONDISCONNECT: self._on_server_disconnect,
            SERVER_ONUPDATE: self._on_server_update
        }
        self._on_update_callback_func = None
        self._on_connect_callback_func = None
        self._on_disconnect_callback_func = None
        self._new_client_callback_func = None

    async def start(self):
        """Initiate server connection."""
        self._is_stopped = False
        await self._do_connect()
        status, error = await self.status()
        if (not isinstance(status, dict)) or ('server' not in status):
            _LOGGER.warning('connected, but no valid response:\n%s', str(error))
            self.stop()
            raise OSError
        _LOGGER.debug('connected to snapserver on %s:%s', self._host, self._port)
        self.synchronize(status)
        self._on_server_connect()

    def stop(self):
        """Stop server."""
        self._is_stopped = True
        self._do_disconnect()
        _LOGGER.debug('Stopping')
        self._clients = {}
        self._streams = {}
        self._groups = {}
        self._version = None

    def _do_disconnect(self):
        """Disconnect from server."""
        if self._transport:
            self._transport.close()

    async def _do_connect(self):
        """Perform the connection to the server."""
        connected = asyncio.Event()

        # actual corutine to handle websocket connection
        async def websocket_handler():
            _LOGGER.debug('try connect to websocket')
            async for self._websocket in websockets.connect(
                        uri=f"ws://{self._host}:{self._port}/jsonrpc"):
                self._protocol = SnapcastWebSocketProtocol(self._websocket, self._callbacks)
                connected.set()
                try:
                    # Receives the replies.
                    async for message in self._websocket:
                        self._protocol.message_received(message)
                except websockets.ConnectionClosed:
                    if self._reconnect and not self._is_stopped:
                        _LOGGER.debug('try reconnect to websocket')
                        continue
                # Closes the connection.
                await self._websocket.close()

        if self._use_websockets:
            self._loop.create_task(websocket_handler())
            await connected.wait()
        else:
            self._transport, self._protocol = await self._loop.create_connection(
                lambda: SnapcastProtocol(self._callbacks), self._host, self._port)

    def _reconnect_cb(self):
        """Try to reconnect to the server."""
        _LOGGER.debug('try reconnect')

        async def try_reconnect():
            """Actual coroutine ro try to reconnect or reschedule."""
            try:
                await self._do_connect()
                status, error = await self.status()
                if (not isinstance(status, dict)) or ('server' not in status):
                    _LOGGER.warning('connected, but no valid response:\n%s', str(error))
                    self.stop()
                    raise OSError
            except OSError:
                self._loop.call_later(SERVER_RECONNECT_DELAY,
                                      self._reconnect_cb)
            else:
                self.synchronize(status)
                self._on_server_connect()
        asyncio.ensure_future(try_reconnect())

    async def _transact(self, method, params=None):
        """Wrap requests."""
        result = error = None
        if self._protocol is None or self._transport is None or self._transport.is_closing():
            error = {"code": None, "message": "Server not connected"}
        else:
            result, error = await self._protocol.request(method, params)
        return (result, error)

    @property
    def version(self):
        """Version."""
        return self._version

    async def status(self):
        """System status."""
        return await self._transact(SERVER_GETSTATUS)

    async def rpc_version(self):
        """RPC version."""
        return await self._transact(SERVER_GETRPCVERSION)

    async def delete_client(self, identifier):
        """Delete client."""
        params = {'id': identifier}
        response, error = await self._transact(SERVER_DELETECLIENT, params)
        if (isinstance(response, dict) and ("server" in response)):
            self.synchronize(response)
        return response, error


    async def client_name(self, identifier, name):
        """Set client name."""
        return await self._request(CLIENT_SETNAME, identifier, 'name', name)

    async def client_latency(self, identifier, latency):
        """Set client latency."""
        return await self._request(CLIENT_SETLATENCY, identifier, 'latency', latency)

    async def client_volume(self, identifier, volume):
        """Set client volume."""
        return await self._request(CLIENT_SETVOLUME, identifier, 'volume', volume)

    async def client_status(self, identifier):
        """Get client status."""
        return await self._request(CLIENT_GETSTATUS, identifier, 'client')

    async def group_status(self, identifier):
        """Get group status."""
        return await self._request(GROUP_GETSTATUS, identifier, 'group')

    async def group_mute(self, identifier, status):
        """Set group mute."""
        return await self._request(GROUP_SETMUTE, identifier, 'mute', status)

    async def group_stream(self, identifier, stream_id):
        """Set group stream."""
        return await self._request(GROUP_SETSTREAM, identifier, 'stream_id', stream_id)

    async def group_clients(self, identifier, clients):
        """Set group clients."""
        return await self._request(GROUP_SETCLIENTS, identifier, 'clients', clients)

    async def group_name(self, identifier, name):
        """Set group name."""
        self._version_check(GROUP_SETNAME)
        return await self._request(GROUP_SETNAME, identifier, 'name', name)

    async def stream_control(self, identifier, control_command, control_params):
        """Set stream control."""
        self._version_check(STREAM_SETPROPERTY)
        return await self._request(
            STREAM_CONTROL, identifier, 'command', control_command, control_params)

    async def stream_setmeta(self, identifier, meta):  # deprecated
        """Set stream metadata."""
        return await self._request(STREAM_SETMETA, identifier, 'meta', meta)

    async def stream_setproperty(self, identifier, stream_property, value):
        """Set stream metadata."""
        self._version_check(STREAM_SETPROPERTY)
        return await self._request(STREAM_SETPROPERTY, identifier, parameters={
            'property': stream_property,
            'value': value
            })

    async def stream_add_stream(self, stream_uri):
        """Add a stream."""
        params = {"streamUri": stream_uri}
        result, error = await self._transact(STREAM_ADDSTREAM, params)
        if (isinstance(result, dict) and ("id" in result)):
            self.synchronize((await self.status())[0])
        return result or error

    async def stream_remove_stream(self, identifier):
        """Remove a Stream."""
        result = await self._request(STREAM_REMOVESTREAM, identifier)
        if (isinstance(result, dict) and ("id" in result)):
            self.synchronize((await self.status())[0])
        return result

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
        self._version = status['server']['server']['snapserver']['version']
        new_groups = {}
        new_clients = {}
        new_streams = {}
        for stream in status.get('server').get('streams'):
            if stream.get('id') in self._streams:
                new_streams[stream.get('id')] = self._streams[stream.get('id')]
                new_streams[stream.get('id')].update(stream)
            else:
                new_streams[stream.get('id')] = Snapstream(stream)
            _LOGGER.debug('stream found: %s', new_streams[stream.get('id')])
        for group in status.get('server').get('groups'):
            if group.get('id') in self._groups:
                new_groups[group.get('id')] = self._groups[group.get('id')]
                new_groups[group.get('id')].update(group)
            else:
                new_groups[group.get('id')] = Snapgroup(self, group)
            for client in group.get('clients'):
                if client.get('id') in self._clients:
                    new_clients[client.get('id')] = self._clients[client.get('id')]
                    new_clients[client.get('id')].update(client)
                else:
                    new_clients[client.get('id')] = Snapclient(self, client)
                _LOGGER.debug('client found: %s', new_clients[client.get('id')])
            _LOGGER.debug('group found: %s', new_groups[group.get('id')])
        self._groups = new_groups
        self._clients = new_clients
        self._streams = new_streams

    # pylint: disable=too-many-arguments
    async def _request(self, method, identifier, key=None, value=None, parameters=None):
        """Perform request with identifier."""
        params = {'id': identifier}
        if key is not None and value is not None:
            params[key] = value
        if isinstance(parameters, dict):
            params.update(parameters)
        result, error = await self._transact(method, params)
        if isinstance(result, dict) and key in result:
            return result.get(key)
        return result or error

    def _on_server_connect(self):
        """Handle server connection."""
        _LOGGER.debug('Server connected')
        if self._on_connect_callback_func and callable(self._on_connect_callback_func):
            self._on_connect_callback_func()

    def _on_server_disconnect(self, exception):
        """Handle server disconnection."""
        _LOGGER.debug('Server disconnected: %s', str(exception))
        if self._on_disconnect_callback_func and callable(self._on_disconnect_callback_func):
            self._on_disconnect_callback_func(exception)
        self._protocol = None
        self._transport = None
        if (not self._is_stopped) and self._reconnect:
            self._reconnect_cb()

    def _on_server_update(self, data):
        """Handle server update."""
        self.synchronize(data)
        if self._on_update_callback_func and callable(self._on_update_callback_func):
            self._on_update_callback_func()

    def _on_group_mute(self, data):
        """Handle group mute."""
        group = self._groups.get(data.get('id'))
        group.update_mute(data)
        for client_id in group.clients:
            self._clients.get(client_id).callback()

    def _on_group_name_changed(self, data):
        """Handle group name changed."""
        self._groups.get(data.get('id')).update_name(data)

    def _on_group_stream_changed(self, data):
        """Handle group stream change."""
        group = self._groups.get(data.get('id'))
        group.update_stream(data)
        for client_id in group.clients:
            self._clients.get(client_id).callback()

    def _on_client_connect(self, data):
        """Handle client connect."""
        client = None
        if data.get('id') in self._clients:
            client = self._clients[data.get('id')]
            client.update_connected(True)
        else:
            client = Snapclient(self, data.get('client'))
            self._clients[data.get('id')] = client
            if self._new_client_callback_func and callable(self._new_client_callback_func):
                self._new_client_callback_func(client)
        _LOGGER.debug('client %s connected', client.friendly_name)

    def _on_client_disconnect(self, data):
        """Handle client disconnect."""
        self._clients[data.get('id')].update_connected(False)
        _LOGGER.debug('client %s disconnected', self._clients[data.get('id')].friendly_name)

    def _on_client_volume_changed(self, data):
        """Handle client volume change."""
        self._clients.get(data.get('id')).update_volume(data)

    def _on_client_name_changed(self, data):
        """Handle client name changed."""
        self._clients.get(data.get('id')).update_name(data)

    def _on_client_latency_changed(self, data):
        """Handle client latency changed."""
        self._clients.get(data.get('id')).update_latency(data)

    def _on_stream_meta(self, data):  # deprecated
        """Handle stream metadata update."""
        if stream := self._streams.get(data.get('id')):
            stream.update_meta(data.get('meta'))
            _LOGGER.debug('stream %s metadata updated', stream.friendly_name)
            for group in self._groups.values():
                if group.stream == data.get('id'):
                    group.callback()

    def _on_stream_properties(self, data):
        """Handle stream properties update."""
        if stream := self._streams.get(data.get('id')):
            stream.update_properties(data.get('properties'))
            _LOGGER.debug('stream %s properties updated', stream.friendly_name)
            for group in self._groups.values():
                if group.stream == data.get('id'):
                    group.callback()
                    for client_id in group.clients:
                        self._clients.get(client_id).callback()

    def _on_stream_update(self, data):
        """Handle stream update."""
        self._streams[data.get('id')].update(data.get('stream'))
        _LOGGER.debug('stream %s updated', self._streams[data.get('id')].friendly_name)
        self._streams[data.get("id")].callback()
        for group in self._groups.values():
            if group.stream == data.get('id'):
                group.callback()
                for client_id in group.clients:
                    self._clients.get(client_id).callback()

    def set_on_update_callback(self, func):
        """Set on update callback function."""
        self._on_update_callback_func = func

    def set_on_connect_callback(self, func):
        """Set on connection callback function."""
        self._on_connect_callback_func = func

    def set_on_disconnect_callback(self, func):
        """Set on disconnection callback function."""
        self._on_disconnect_callback_func = func

    def set_new_client_callback(self, func):
        """Set new client callback function."""
        self._new_client_callback_func = func

    def __repr__(self):
        """Return string representation."""
        return f'Snapserver {self.version} ({self._host})'

    def _version_check(self, api_call):
        if version.parse(self.version) < version.parse(_VERSIONS.get(api_call)):
            raise ServerVersionError(
                f"{api_call} requires server version >= {_VERSIONS[api_call]}."
                + f" Current version is {self.version}"
            )
