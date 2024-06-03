"""Snapcast server."""

import asyncio
import logging

from packaging import version
from snapcast.control.client import Snapclient
from snapcast.control.group import Snapgroup
from snapcast.control.protocol import SERVER_ONDISCONNECT, SnapcastProtocol
from snapcast.control.stream import Snapstream
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

_LOGGER = logging.getLogger(__name__)

CONTROL_PORT = 1705

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


# pylint: disable=too-many-public-methods

class Snapserver:
    """Represents a snapserver."""

    # pylint: disable=too-many-instance-attributes
    def __init__(self, loop: asyncio.AbstractEventLoop, host: str, port: int = CONTROL_PORT, reconnect: bool = False) -> None:
        """Initialize."""
        self._loop: asyncio.AbstractEventLoop = loop
        self._port: int = port
        self._reconnect: bool = reconnect
        self._is_stopped: bool = True
        self._clients: Dict[str, Any] = {}
        self._streams: Dict[str, Any] = {}
        self._groups: Dict[str, Any] = {}
        self._host: str = host
        self._version: Optional[str] = None
        self._protocol: Optional[Any] = None
        self._transport: Optional[asyncio.Transport] = None
        self._callbacks: Dict[str, Callable[[Any], None]] = {
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
        self._on_update_callback_func: Optional[Callable[[], None]] = None
        self._on_connect_callback_func: Optional[Callable[[], None]] = None
        self._on_disconnect_callback_func: Optional[Callable[[Optional[Exception]], None]] = None
        self._new_client_callback_func: Optional[Callable[[Any], None]] = None

    async def start(self) -> None:
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

    def stop(self) -> None:
        """Stop server connection."""
        self._is_stopped = True
        self._do_disconnect()
        _LOGGER.debug('Stopping')
        self._clients = {}
        self._streams = {}
        self._groups = {}
        self._version = None

    def _do_disconnect(self) -> None:
        """Perform the connection to the server."""
        if self._transport:
            self._transport.close()

    async def _do_connect(self) -> None:
        """Perform the connection to the server."""
        self._transport, self._protocol = await self._loop.create_connection(
            lambda: SnapcastProtocol(self._callbacks), self._host, self._port)

    def _reconnect_cb(self) -> None:
        """Try to reconnect to the server."""
        _LOGGER.debug('try reconnect')

        async def try_reconnect() -> None:
            """Actual coroutine to try to reconnect or reschedule.
            
                Raises:
                    OSError: If there isn't a valid response from the server.
            """
            try:
                await self._do_connect()
                status, error = await self.status()
                if (not isinstance(status, dict)) or ('server' not in status):
                    _LOGGER.warning('connected, but no valid response:\n%s', str(error))
                    self.stop()
                    raise OSError
            except OSError:
                self._loop.call_later(SERVER_RECONNECT_DELAY, self._reconnect_cb)
            else:
                self.synchronize(status)
                self._on_server_connect()
        asyncio.ensure_future(try_reconnect())

    async def _transact(self, method: str, params: Optional[Dict[str, Any]] = None) -> Tuple[Optional[Any], Optional[Dict[str, Any]]]:
        """Wrap requests."""
        result = error = None
        if self._protocol is None or self._transport is None or self._transport.is_closing():
            error = {"code": None, "message": "Server not connected"}
        else:
            result, error = await self._protocol.request(method, params)
        return result, error

    @property
    def version(self) -> Optional[str]:
        """Get server version."""
        return self._version

    async def status(self) -> Tuple[Optional[Any], Optional[Dict[str, Any]]]:
        """Get system status."""
        return await self._transact(SERVER_GETSTATUS)

    async def rpc_version(self) -> Tuple[Optional[Any], Optional[Dict[str, Any]]]:
        """Get RPC version."""
        return await self._transact(SERVER_GETRPCVERSION)

    async def delete_client(self, identifier: str) -> None:
        """Delete client from the server."""
        params = {'id': identifier}
        response, _ = await self._transact(SERVER_DELETECLIENT, params)
        self.synchronize(response)

    async def client_name(self, identifier: str, name: str) -> Tuple[Optional[Any], Optional[Dict[str, Any]]]:
        """Set client name."""
        return await self._request(CLIENT_SETNAME, identifier, 'name', name)

    async def client_latency(self, identifier: str, latency: int) -> Tuple[Optional[Any], Optional[Dict[str, Any]]]:
        """Set client latency."""
        return await self._request(CLIENT_SETLATENCY, identifier, 'latency', latency)

    async def client_volume(self, identifier: str, volume: int) -> Tuple[Optional[Any], Optional[Dict[str, Any]]]:
        """Set client volume."""
        return await self._request(CLIENT_SETVOLUME, identifier, 'volume', volume)

    async def client_status(self, identifier: str) -> Tuple[Optional[Any], Optional[Dict[str, Any]]]:
        """Get client status."""
        return await self._request(CLIENT_GETSTATUS, identifier, 'client')

    async def group_status(self, identifier: str) -> Tuple[Optional[Any], Optional[Dict[str, Any]]]:
        """Get group status."""
        return await self._request(GROUP_GETSTATUS, identifier, 'group')

    async def group_mute(self, identifier: str, status: bool) -> Tuple[Optional[Any], Optional[Dict[str, Any]]]:
        """Set group mute."""
        return await self._request(GROUP_SETMUTE, identifier, 'mute', status)

    async def group_stream(self, identifier: str, stream_id: str) -> Tuple[Optional[Any], Optional[Dict[str, Any]]]:
        """Set group stream."""
        return await self._request(GROUP_SETSTREAM, identifier, 'stream_id', stream_id)

    async def group_clients(self, identifier: str, clients: List[str]) -> Tuple[Optional[Any], Optional[Dict[str, Any]]]:
        """Set group clients."""
        return await self._request(GROUP_SETCLIENTS, identifier, 'clients', clients)

    async def group_name(self, identifier: str, name: str) -> Tuple[Optional[Any], Optional[Dict[str, Any]]]:
        """Set group name."""
        self._version_check(GROUP_SETNAME)
        return await self._request(GROUP_SETNAME, identifier, 'name', name)

    async def stream_control(self, identifier: str, control_command: str, control_params: Dict[str, Any]) -> Tuple[Optional[Any], Optional[Dict[str, Any]]]:
        """Set stream control."""
        self._version_check(STREAM_SETPROPERTY)
        return await self._request(STREAM_CONTROL, identifier, 'command', control_command, control_params)

    async def stream_setmeta(self, identifier: str, meta: Dict[str, Any]) -> Tuple[Optional[Any], Optional[Dict[str, Any]]]:  # deprecated
        """Set stream metadata."""
        return await self._request(STREAM_SETMETA, identifier, 'meta', meta)

    async def stream_setproperty(self, identifier: str, stream_property: str, value: Any) -> Tuple[Optional[Any], Optional[Dict[str, Any]]]:
        """Set stream metadata."""
        self._version_check(STREAM_SETPROPERTY)
        return await self._request(STREAM_SETPROPERTY, identifier, parameters={
            'property': stream_property,
            'value': value
            })

    async def stream_add_stream(self, stream_uri: str) -> Tuple[Optional[Any], Optional[Dict[str, Any]]]:
        """Add a stream."""
        params = {"streamUri": stream_uri}
        result, error = await self._transact(STREAM_ADDSTREAM, params)
        if isinstance(result, dict) and ("id" in result):
            self.synchronize((await self.status())[0])
        return result or error

    async def stream_remove_stream(self, identifier: str) -> Tuple[Optional[Any], Optional[Dict[str, Any]]]:
        """Remove a Stream from the server."""
        result = await self._request(STREAM_REMOVESTREAM, identifier)
        if isinstance(result, dict) and ("id" in result):
            self.synchronize((await self.status())[0])
        return result

    def group(self, group_identifier: str) -> Any:
        """Get a group."""
        return self._groups[group_identifier]

    def stream(self, stream_identifier: str) -> Any:
        """Get a stream."""
        return self._streams[stream_identifier]

    def client(self, client_identifier: str) -> Any:
        """Get a client."""
        return self._clients[client_identifier]

    @property
    def groups(self) -> List[Any]:
        """Get groups."""
        return list(self._groups.values())

    @property
    def clients(self) -> List[Any]:
        """Get clients."""
        return list(self._clients.values())

    @property
    def streams(self) -> List[Any]:
        """Get streams."""
        return list(self._streams.values())

    def synchronize(self, status: Dict[str, Any]) -> None:
        """Synchronize snapserver."""
        self._version = status['server']['server']['snapserver']['version']
        new_groups: Dict[str, Any] = {}
        new_clients: Dict[str, Any] = {}
        new_streams: Dict[str, Any] = {}
        for stream in status.get('server', {}).get('streams', []):
            if stream.get('id') in self._streams:
                new_streams[stream.get('id')] = self._streams[stream.get('id')]
                new_streams[stream.get('id')].update(stream)
            else:
                new_streams[stream.get('id')] = Snapstream(stream)
            _LOGGER.debug('stream found: %s', new_streams[stream.get('id')])
        for group in status.get('server', {}).get('groups', []):
            if group.get('id') in self._groups:
                new_groups[group.get('id')] = self._groups[group.get('id')]
                new_groups[group.get('id')].update(group)
            else:
                new_groups[group.get('id')] = Snapgroup(self, group)
            for client in group.get('clients', []):
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
    async def _request(self, method: str, identifier: str, key: Optional[str] = None, value: Optional[Any] = None, parameters: Optional[Dict[str, Any]] = None) -> Tuple[Optional[Any], Optional[Dict[str, Any]]]:
        """Perform request with identifier."""
        params = {'id': identifier}
        if key is not None and value is not None:
            params[key] = value
        if isinstance(parameters, dict):
            params.update(parameters)
        result, error = await self._transact(method, params)
        if isinstance(result, dict) and key in result:
            return result.get(key), None
        return result, error

    def _on_server_connect(self) -> None:
        """Handle server connection."""
        _LOGGER.debug('Server connected')
        if self._on_connect_callback_func and callable(self._on_connect_callback_func):
            self._on_connect_callback_func()

    def _on_server_disconnect(self, exception: Optional[Exception]) -> None:
        """Handle server disconnection."""
        _LOGGER.debug('Server disconnected: %s', str(exception))
        if self._on_disconnect_callback_func and callable(self._on_disconnect_callback_func):
            self._on_disconnect_callback_func(exception)
        self._protocol = None
        self._transport = None
        if (not self._is_stopped) and self._reconnect:
            self._reconnect_cb()

    def _on_server_update(self, data: Dict[str, Any]) -> None:
        """Handle server update."""
        self.synchronize(data)
        if self._on_update_callback_func and callable(self._on_update_callback_func):
            self._on_update_callback_func()

    def _on_group_mute(self, data: Dict[str, Any]) -> None:
        """Handle group mute."""
        group = self._groups.get(data.get('id'))
        if group:
            group.update_mute(data)
            for client_id in group.clients:
                self._clients.get(client_id).callback()

    def _on_group_name_changed(self, data: Dict[str, Any]) -> None:
        """Handle group name changed."""
        if data.get('id') in self._groups:
            self._groups[data.get('id')].update_name(data)

    def _on_group_stream_changed(self, data: Dict[str, Any]) -> None:
        """Handle group stream change."""
        group = self._groups.get(data.get('id'))
        if group:
            group.update_stream(data)
            for client_id in group.clients:
                self._clients.get(client_id).callback()

    def _on_client_connect(self, data: Dict[str, Any]) -> None:
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

    def _on_client_disconnect(self, data: Dict[str, Any]) -> None:
        """Handle client disconnect."""
        if data.get('id') in self._clients:
            self._clients[data.get('id')].update_connected(False)
            _LOGGER.debug('client %s disconnected', self._clients[data.get('id')].friendly_name)

    def _on_client_volume_changed(self, data: Dict[str, Any]) -> None:
        """Handle client volume change."""
        if data.get('id') in self._clients:
            self._clients.get(data.get('id')).update_volume(data)

    def _on_client_name_changed(self, data: Dict[str, Any]) -> None:
        """Handle client name changed."""
        if data.get('id') in self._clients:
            self._clients.get(data.get('id')).update_name(data)

    def _on_client_latency_changed(self, data: Dict[str, Any]) -> None:
        """Handle client latency changed."""
        if data.get('id') in self._clients:
            self._clients.get(data.get('id')).update_latency(data)

    def _on_stream_meta(self, data: Dict[str, Any]) -> None:  # deprecated
        """Handle stream metadata update."""
        stream = self._streams[data.get('id')]
        stream.update_meta(data.get('meta'))
        _LOGGER.debug('stream %s metadata updated', stream.friendly_name)
        for group in self._groups.values():
            if group.stream == data.get('id'):
                group.callback()

    def _on_stream_properties(self, data: Dict[str, Any]) -> None:
        """Handle stream properties update."""
        stream = self._streams[data.get('id')]
        stream.update_properties(data.get('properties'))
        _LOGGER.debug('stream %s properties updated', stream.friendly_name)
        for group in self._groups.values():
            if group.stream == data.get('id'):
                group.callback()
                for client_id in group.clients:
                    self._clients.get(client_id).callback()

    def _on_stream_update(self, data: Dict[str, Any]) -> None:
        """Handle stream update."""
        if data.get('id') in self._streams:
            self._streams[data.get('id')].update(data.get('stream'))
            _LOGGER.debug('stream %s updated', self._streams[data.get('id')].friendly_name)
            self._streams[data.get("id")].callback()
            for group in self._groups.values():
                if group.stream == data.get('id'):
                    group.callback()
                    for client_id in group.clients:
                        self._clients.get(client_id).callback()
        else:
            if data.get('stream', {}).get('uri', {}).get('query', {}).get('codec') == 'null':
                _LOGGER.debug('stream %s is input-only, ignore', data.get('id'))
            else:
                _LOGGER.info('stream %s not found, synchronize', data.get('id'))

                async def async_sync() -> None:
                    self.synchronize((await self.status())[0])
                asyncio.ensure_future(async_sync())

    def set_on_update_callback(self, func: Callable[[], None]) -> None:
        """Set on update callback function."""
        self._on_update_callback_func = func

    def set_on_connect_callback(self, func: Callable[[], None]) -> None:
        """Set on connection callback function."""
        self._on_connect_callback_func = func

    def set_on_disconnect_callback(self, func: Callable[[Optional[Exception]], None]) -> None:
        """Set on disconnection callback function."""
        self._on_disconnect_callback_func = func

    def set_new_client_callback(self, func: Callable[[Any], None]) -> None:
        """Set new client callback function."""
        self._new_client_callback_func = func

    def __repr__(self) -> str:
        """Return string representation of the server."""
        return f'Snapserver {self.version} ({self._host})'

    def _version_check(self, api_call: str) -> None:
        """
        Checks if the server version meets the minimum requirement for a given API call.

        Raises:
            ServerVersionError: If the server version is lower than the required version for the API call.
        """
        if version.parse(self.version) < version.parse(_VERSIONS.get(api_call)):
            raise ServerVersionError(
                f"{api_call} requires server version >= {_VERSIONS[api_call]}."
                + f" Current version is {self.version}"
            )
