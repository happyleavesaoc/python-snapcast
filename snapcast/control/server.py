"""Snapcast server."""

import asyncio
import logging

from packaging import version

from snapcast.control.client import Snapclient
from snapcast.control.group import Snapgroup
from snapcast.control.protocol import SERVER_ONDISCONNECT, SnapcastProtocol
from snapcast.control.stream import Snapstream

_LOGGER = logging.getLogger(__name__)

CONTROL_PORT = 1705

SERVER_GETSTATUS = "Server.GetStatus"
SERVER_GETRPCVERSION = "Server.GetRPCVersion"
SERVER_DELETECLIENT = "Server.DeleteClient"
SERVER_ONUPDATE = "Server.OnUpdate"

CLIENT_GETSTATUS = "Client.GetStatus"
CLIENT_SETNAME = "Client.SetName"
CLIENT_SETLATENCY = "Client.SetLatency"
CLIENT_SETVOLUME = "Client.SetVolume"
CLIENT_ONCONNECT = "Client.OnConnect"
CLIENT_ONDISCONNECT = "Client.OnDisconnect"
CLIENT_ONVOLUMECHANGED = "Client.OnVolumeChanged"
CLIENT_ONLATENCYCHANGED = "Client.OnLatencyChanged"
CLIENT_ONNAMECHANGED = "Client.OnNameChanged"

GROUP_GETSTATUS = "Group.GetStatus"
GROUP_SETMUTE = "Group.SetMute"
GROUP_SETSTREAM = "Group.SetStream"
GROUP_SETCLIENTS = "Group.SetClients"
GROUP_SETNAME = "Group.SetName"
GROUP_ONMUTE = "Group.OnMute"
GROUP_ONSTREAMCHANGED = "Group.OnStreamChanged"
GROUP_ONNAMECHANGED = "Group.OnNameChanged"


STREAM_ONPROPERTIES = "Stream.OnProperties"
STREAM_SETPROPERTY = "Stream.SetProperty"
STREAM_CONTROL = "Stream.Control"  # not yet implemented
STREAM_SETMETA = "Stream.SetMeta"  # deprecated
STREAM_ONUPDATE = "Stream.OnUpdate"
STREAM_ONMETA = "Stream.OnMetadata"  # deprecated
STREAM_ADDSTREAM = "Stream.AddStream"
STREAM_REMOVESTREAM = "Stream.RemoveStream"

SERVER_RECONNECT_DELAY = 5

_EVENTS = [
    SERVER_ONUPDATE,
    CLIENT_ONVOLUMECHANGED,
    CLIENT_ONLATENCYCHANGED,
    CLIENT_ONNAMECHANGED,
    CLIENT_ONCONNECT,
    CLIENT_ONDISCONNECT,
    GROUP_ONMUTE,
    GROUP_ONSTREAMCHANGED,
    GROUP_ONNAMECHANGED,
    STREAM_ONUPDATE,
    STREAM_ONMETA,
    STREAM_ONPROPERTIES,
]
_METHODS = [
    SERVER_GETSTATUS,
    SERVER_GETRPCVERSION,
    SERVER_DELETECLIENT,
    SERVER_DELETECLIENT,
    CLIENT_GETSTATUS,
    CLIENT_SETNAME,
    CLIENT_SETLATENCY,
    CLIENT_SETVOLUME,
    GROUP_GETSTATUS,
    GROUP_SETMUTE,
    GROUP_SETSTREAM,
    GROUP_SETCLIENTS,
    GROUP_SETNAME,
    STREAM_SETMETA,
    STREAM_SETPROPERTY,
    STREAM_CONTROL,
    STREAM_ADDSTREAM,
    STREAM_REMOVESTREAM,
]

# server versions in which new methods were added
_VERSIONS = {
    GROUP_SETNAME: "0.16.0",
    STREAM_SETPROPERTY: "0.26.0",
    STREAM_ADDSTREAM: "0.16.0",
    STREAM_REMOVESTREAM: "0.16.0",
}


class ServerVersionError(NotImplementedError):
    """Server Version Error, not implemented."""


# pylint: disable=too-many-public-methods
class Snapserver:
    """
    Represents a Snapserver instance.

    This class provides methods to interact with a Snapserver instance, such as starting and stopping the server,
    retrieving server status, managing clients, groups, and streams, and performing various operations on them.

    Args:
        loop (asyncio.AbstractEventLoop): The event loop to use for asynchronous operations.
        host (str): The hostname or IP address of the Snapserver.
        port (int, optional): The port number of the Snapserver control interface. Defaults to CONTROL_PORT.
        reconnect (bool, optional): Whether to automatically reconnect to the Snapserver if the connection is lost.
            Defaults to False.

    Attributes:
        version (str): The version of the Snapserver.
        groups (list): A list of Snapgroup objects representing the groups in the Snapserver.
        clients (list): A list of Snapclient objects representing the clients connected to the Snapserver.
        streams (list): A list of Snapstream objects representing the streams available in the Snapserver.

    """

    # pylint: disable=too-many-instance-attributes
    def __init__(self, loop, host, port=CONTROL_PORT, reconnect=False):
        """Initialize."""
        self._loop = loop
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
            SERVER_ONUPDATE: self._on_server_update,
        }
        self._on_update_callback_func = None
        self._on_connect_callback_func = None
        self._on_disconnect_callback_func = None
        self._new_client_callback_func = None

    async def start(self):
        """Initiate server connection.

        This method is used to establish a connection with the server.
        It performs the necessary steps to connect to the server and
        checks for a valid response. If the response is not valid, it
        raises an OSError.

        Raises:
            OSError: If the server response is not valid.

        """
        self._is_stopped = False
        await self._do_connect()
        status, error = await self.status()
        if (not isinstance(status, dict)) or ("server" not in status):
            _LOGGER.warning("connected, but no valid response:\n%s", str(error))
            self.stop()
            raise OSError
        _LOGGER.debug("connected to snapserver on %s:%s", self._host, self._port)
        self.synchronize(status)
        self._on_server_connect()

    def stop(self):
        """Stop server.

        This method stops the server by setting the `_is_stopped` flag to True,
        disconnecting all clients, and resetting internal data structures.

        """
        self._is_stopped = True
        self._do_disconnect()
        _LOGGER.debug("Stopping")
        self._clients = {}
        self._streams = {}
        self._groups = {}
        self._version = None

    def _do_disconnect(self):
        """Perform the disconnection from the server.

        This method closes the transport connection to the server if it exists.
        """
        if self._transport:
            self._transport.close()

    async def _do_connect(self):
        """Perform the connection to the server.

        This method establishes a connection to the Snapcast server using the specified host and port.
        It creates a transport and protocol using the asyncio `create_connection` method.
        The `SnapcastProtocol` class is used as the protocol for handling communication with the server.
        The `_callbacks` parameter is passed to the `SnapcastProtocol` constructor to handle callbacks.

        Returns:
            None

        """
        self._transport, self._protocol = await self._loop.create_connection(
            lambda: SnapcastProtocol(self._callbacks), self._host, self._port
        )

    def _reconnect_cb(self):
        """Try to reconnect to the server.

        This method is called when a connection to the server is lost and
        attempts to reconnect to the server. It first tries to establish a
        new connection and then checks if the server responds with a valid
        status. If the response is not valid, it logs a warning and stops
        the connection. If the connection is successful and the status is
        valid, it synchronizes the status and triggers the `_on_server_connect`
        method.

        """
        _LOGGER.debug("try reconnect")

        async def try_reconnect():
            """Actual coroutine to try to reconnect or reschedule.

            This function attempts to reconnect to the server or reschedule the reconnection
            based on the response received. If a valid response is received, the status is
            synchronized and the `_on_server_connect` method is called. If no valid response
            is received, a warning is logged and the connection is stopped.

            Raises:
                OSError: If no valid response is received after reconnecting.

            """
            try:
                await self._do_connect()
                status, error = await self.status()
                if (not isinstance(status, dict)) or ("server" not in status):
                    _LOGGER.warning("connected, but no valid response:\n%s", str(error))
                    self.stop()
                    raise OSError
            except OSError:
                self._loop.call_later(SERVER_RECONNECT_DELAY, self._reconnect_cb)
            else:
                self.synchronize(status)
                self._on_server_connect()

        asyncio.ensure_future(try_reconnect())

    async def _transact(self, method, params=None):
        """Wrap requests.

        This method wraps requests made to the server. It checks if the server is connected,
        and if so, it sends the request using the `_protocol` and `_transport` attributes.
        If the server is not connected, it returns an error indicating that the server is not connected.

        Args:
            method (str): The method to be requested.
            params (dict, optional): The parameters to be sent with the request.

        Returns:
            tuple: A tuple containing the result and error of the request.

        """
        result = error = None
        if (
            self._protocol is None
            or self._transport is None
            or self._transport.is_closing()
        ):
            error = {"code": None, "message": "Server not connected"}
        else:
            result, error = await self._protocol.request(method, params)
        return (result, error)

    @property
    def version(self):
        """
        Return the version of the server.

        Returns:
            str: The version of the server.
        """
        return self._version

    async def status(self):
        """
        System status.

        Returns:
            The system status.

        """
        return await self._transact(SERVER_GETSTATUS)

    async def rpc_version(self):
        """
        RPC version.

        Returns:
            The version of the RPC.

        """
        return await self._transact(SERVER_GETRPCVERSION)

    async def delete_client(self, identifier):
        """Delete a client.

        Args:
            identifier (str): The identifier of the client to be deleted.

        """
        params = {"id": identifier}
        response, _ = await self._transact(SERVER_DELETECLIENT, params)
        self.synchronize(response)

    async def client_name(self, identifier, name):
        """
        Set client name.

        Args:
            identifier (str): The identifier of the client.
            name (str): The name to set for the client.

        Returns:
            The result of the request.

        """
        return await self._request(CLIENT_SETNAME, identifier, "name", name)

    async def client_latency(self, identifier, latency):
        """
        Set client latency.

        Args:
            identifier (str): The identifier of the client.
            latency (int): The latency value to set.

        Returns:
            The result of the request.

        """
        return await self._request(CLIENT_SETLATENCY, identifier, "latency", latency)

    async def client_volume(self, identifier, volume):
        """
        Set client volume.

        Args:
            identifier (str): The identifier of the client.
            volume (int): The volume level to set.

        Returns:
            The result of the request.

        """
        return await self._request(CLIENT_SETVOLUME, identifier, "volume", volume)

    async def client_status(self, identifier):
        """
        Get client status.

        Args:
            identifier (str): The identifier of the client.

        Returns:
            dict: A dictionary containing the status of the client.

        """
        return await self._request(CLIENT_GETSTATUS, identifier, "client")

    async def group_status(self, identifier):
        """
        Get group status.

        Args:
            identifier (str): The identifier of the group.

        Returns:
            dict: The status of the group.

        """
        return await self._request(GROUP_GETSTATUS, identifier, "group")

    async def group_mute(self, identifier, status):
        """
        Set group mute.

        Args:
            identifier (str): The identifier of the group.
            status (bool): The mute status to set.

        Returns:
            The result of the request.

        """
        return await self._request(GROUP_SETMUTE, identifier, "mute", status)

    async def group_stream(self, identifier, stream_id):
        """
        Set group stream.

        Args:
            identifier (str): The identifier of the group.
            stream_id (str): The ID of the stream to set.

        Returns:
            The result of the request.

        """
        return await self._request(GROUP_SETSTREAM, identifier, "stream_id", stream_id)

    async def group_clients(self, identifier, clients):
        """
        Set group clients.

        Args:
            identifier (str): The identifier of the group.
            clients (list): A list of client identifiers to be added to the group.

        Returns:
            The result of the request.

        """
        return await self._request(GROUP_SETCLIENTS, identifier, "clients", clients)

    async def group_name(self, identifier, name):
        """
        Set the name of a group.

        Args:
            identifier (str): The identifier of the group.
            name (str): The new name for the group.

        Returns:
            The result of the request.

        Raises:
            VersionMismatchError: If the server version does not support the GROUP_SETNAME command.
        """
        self._version_check(GROUP_SETNAME)
        return await self._request(GROUP_SETNAME, identifier, "name", name)

    async def stream_control(self, identifier, control_command, control_params):
        """
        Set stream control.

        Args:
            identifier (str): The identifier of the stream.
            control_command (str): The control command to be executed.
            control_params (dict): Additional parameters for the control command.

        Returns:
            The response from the server.

        Raises:
            VersionError: If the server version does not support stream control.

        """
        self._version_check(STREAM_SETPROPERTY)
        return await self._request(
            STREAM_CONTROL, identifier, "command", control_command, control_params
        )

    async def stream_setmeta(self, identifier, meta):  # deprecated
        """Set stream metadata."""
        return await self._request(STREAM_SETMETA, identifier, "meta", meta)

    async def stream_setproperty(self, identifier, stream_property, value):
        """
        Set stream metadata.

        Args:
            identifier (str): The identifier of the stream.
            stream_property (str): The property to set.
            value: The value to set for the property.

        Returns:
            The response from the server.

        """
        self._version_check(STREAM_SETPROPERTY)
        return await self._request(
            STREAM_SETPROPERTY,
            identifier,
            parameters={"property": stream_property, "value": value},
        )

    async def stream_add_stream(self, stream_uri):
        """
        Add a stream.

        Args:
            stream_uri (str): The URI of the stream to be added.

        Returns:
            dict or str: The result of adding the stream. If successful, a dictionary
            containing the stream ID will be returned. If unsuccessful, an error message
            will be returned.

        """
        params = {"streamUri": stream_uri}
        result, error = await self._transact(STREAM_ADDSTREAM, params)
        if isinstance(result, dict) and ("id" in result):
            self.synchronize((await self.status())[0])
        return result or error

    async def stream_remove_stream(self, identifier):
        """
        Remove a Stream.

        Args:
            identifier (str): The identifier of the stream to be removed.

        Returns:
            dict: The result of the removal operation.

        """
        result = await self._request(STREAM_REMOVESTREAM, identifier)
        if isinstance(result, dict) and ("id" in result):
            self.synchronize((await self.status())[0])
        return result

    def group(self, group_identifier):
        """
        Get a group.

        Args:
            group_identifier (str): The identifier of the group.

        Returns:
            Group: The group object.

        """
        return self._groups[group_identifier]

    def stream(self, stream_identifier):
        """
        Get a stream.

        Args:
            stream_identifier (str): The identifier of the stream.

        Returns:
            Stream: The stream object corresponding to the given identifier.
        """
        return self._streams[stream_identifier]

    def client(self, client_identifier):
        """
        Get a client.

        Args:
            client_identifier (str): The identifier of the client.

        Returns:
            Client: The client object corresponding to the given identifier.
        """
        return self._clients[client_identifier]

    @property
    def groups(self):
        """
        Get groups.

        Returns:
            list: A list of groups.
        """
        return list(self._groups.values())

    @property
    def clients(self):
        """
        Get clients.

        Returns:
            list: A list of clients.
        """
        return list(self._clients.values())

    @property
    def streams(self):
        """
        Get streams.

        Returns:
            list: A list of streams.
        """
        return list(self._streams.values())

    def synchronize(self, status):
        """
        Synchronize snapserver.

        This method synchronizes the snapserver with the provided status.
        It updates the internal state of the server, including the version,
        groups, clients, and streams.

        Args:
            status (dict): The status of the snapserver.

        Returns:
            None
        """
        self._version = status["server"]["server"]["snapserver"]["version"]
        new_groups = {}
        new_clients = {}
        new_streams = {}
        for stream in status.get("server").get("streams"):
            if stream.get("id") in self._streams:
                new_streams[stream.get("id")] = self._streams[stream.get("id")]
                new_streams[stream.get("id")].update(stream)
            else:
                new_streams[stream.get("id")] = Snapstream(stream)
            _LOGGER.debug("stream found: %s", new_streams[stream.get("id")])
        for group in status.get("server").get("groups"):
            if group.get("id") in self._groups:
                new_groups[group.get("id")] = self._groups[group.get("id")]
                new_groups[group.get("id")].update(group)
            else:
                new_groups[group.get("id")] = Snapgroup(self, group)
            for client in group.get("clients"):
                if client.get("id") in self._clients:
                    new_clients[client.get("id")] = self._clients[client.get("id")]
                    new_clients[client.get("id")].update(client)
                else:
                    new_clients[client.get("id")] = Snapclient(self, client)
                _LOGGER.debug("client found: %s", new_clients[client.get("id")])
            _LOGGER.debug("group found: %s", new_groups[group.get("id")])
        self._groups = new_groups
        self._clients = new_clients
        self._streams = new_streams

    # pylint: disable=too-many-arguments
    async def _request(self, method, identifier, key=None, value=None, parameters=None):
        """
        Perform a request with the given identifier.

        Args:
            method (str): The HTTP method to use for the request.
            identifier (str): The identifier for the request.
            key (str, optional): The key for the request parameter. Defaults to None.
            value (str, optional): The value for the request parameter. Defaults to None.
            parameters (dict, optional): Additional parameters for the request. Defaults to None.

        Returns:
            The result of the request, or an error if the request failed.
        """
        params = {"id": identifier}
        if key is not None and value is not None:
            params[key] = value
        if isinstance(parameters, dict):
            params.update(parameters)
        result, error = await self._transact(method, params)
        if isinstance(result, dict) and key in result:
            return result.get(key)
        return result or error

    def _on_server_connect(self):
        """
        Handle server connection.

        This method is called when the server is successfully connected.
        It logs a debug message and invokes the `_on_connect_callback_func` if it is callable.

        """
        _LOGGER.debug("Server connected")
        if self._on_connect_callback_func and callable(self._on_connect_callback_func):
            self._on_connect_callback_func()

    def _on_server_disconnect(self, exception):
        """
        Handle server disconnection.

        Args:
            exception: The exception that caused the disconnection.

        Returns:
            None
        """
        _LOGGER.debug("Server disconnected: %s", str(exception))
        if self._on_disconnect_callback_func and callable(
            self._on_disconnect_callback_func
        ):
            self._on_disconnect_callback_func(exception)
        self._protocol = None
        self._transport = None
        if (not self._is_stopped) and self._reconnect:
            self._reconnect_cb()

    def _on_server_update(self, data):
        """
        Handle server update.

        This method is responsible for handling updates received from the server.
        It synchronizes the data and calls the update callback function if it is defined.

        Args:
            data: The data received from the server.

        Returns:
            None
        """
        self.synchronize(data)
        if self._on_update_callback_func and callable(self._on_update_callback_func):
            self._on_update_callback_func()

    def _on_group_mute(self, data):
        """
        Handle group mute.

        This method is responsible for handling the mute event of a group.
        It updates the mute status of the group and triggers a callback for each client in the group.

        Args:
            data (dict): The data containing the group ID and mute status.

        Returns:
            None
        """
        group = self._groups.get(data.get("id"))
        group.update_mute(data)
        for client_id in group.clients:
            self._clients.get(client_id).callback()

    def _on_group_name_changed(self, data):
        """
        Handle group name changed.

        This method is called when the name of a group is changed. It updates the name of the group
        with the new data provided.

        Args:
            data (dict): A dictionary containing the updated group information.

        Returns:
            None
        """
        self._groups.get(data.get("id")).update_name(data)

    def _on_group_stream_changed(self, data):
        """
        Handle group stream change.

        This method is called when there is a change in the stream of a group.
        It updates the stream data for the corresponding group and triggers a callback
        for each client in the group.

        Args:
            data (dict): The data containing the information about the stream change.
        """
        group = self._groups.get(data.get("id"))
        group.update_stream(data)
        for client_id in group.clients:
            self._clients.get(client_id).callback()

    def _on_client_connect(self, data):
        """
        Handle client connect.

        This method is called when a client connects to the server. It updates the
        connection status of the client and creates a new `Snapclient` instance if
        the client is not already present in the `_clients` dictionary.

        Args:
            data (dict): A dictionary containing the client data, including the client ID.
        """
        client = None
        if data.get("id") in self._clients:
            client = self._clients[data.get("id")]
            client.update_connected(True)
        else:
            client = Snapclient(self, data.get("client"))
            self._clients[data.get("id")] = client
            if self._new_client_callback_func and callable(
                self._new_client_callback_func
            ):
                self._new_client_callback_func(client)
        _LOGGER.debug("client %s connected", client.friendly_name)

    def _on_client_disconnect(self, data):
        """
        Handle client disconnect.

        This method is called when a client disconnects from the server.
        It updates the connected status of the client and logs a debug message.

        Args:
            data (dict): A dictionary containing information about the disconnected client.
        """
        self._clients[data.get("id")].update_connected(False)
        _LOGGER.debug(
            "client %s disconnected", self._clients[data.get("id")].friendly_name
        )

    def _on_client_volume_changed(self, data):
        """
        Handle client volume change.

        This method is called when the volume of a client is changed.
        It updates the volume of the corresponding client object.

        Args:
            data (dict): A dictionary containing the volume change information.
        """
        self._clients.get(data.get("id")).update_volume(data)

    def _on_client_name_changed(self, data):
        """
        Handle client name changed.

        Args:
            data (dict): The data containing the client ID and the updated name.
        """
        self._clients.get(data.get("id")).update_name(data)

    def _on_client_latency_changed(self, data):
        """
        Handle client latency changed.

        This method is called when the latency of a client changes. It updates the latency information
        for the corresponding client.

        Args:
            data (dict): A dictionary containing the updated latency information for the client.
        """
        self._clients.get(data.get("id")).update_latency(data)

    def _on_stream_meta(self, data):  # deprecated
        """Handle stream metadata update."""
        stream = self._streams[data.get("id")]
        stream.update_meta(data.get("meta"))
        _LOGGER.debug("stream %s metadata updated", stream.friendly_name)
        for group in self._groups.values():
            if group.stream == data.get("id"):
                group.callback()

    def _on_stream_properties(self, data):
        """
        Handle stream properties update.

        This method is called when the properties of a stream are updated.
        It updates the properties of the corresponding stream object and triggers
        the callback functions for the affected groups and clients.

        Args:
            data (dict): A dictionary containing the updated stream properties.
        """
        stream = self._streams[data.get("id")]
        stream.update_properties(data.get("properties"))
        _LOGGER.debug("stream %s properties updated", stream.friendly_name)
        for group in self._groups.values():
            if group.stream == data.get("id"):
                group.callback()
                for client_id in group.clients:
                    self._clients.get(client_id).callback()

    def _on_stream_update(self, data):
        """
        Handle stream update.

        This method is called when a stream update event is received. It updates the
        corresponding stream object with the new data, triggers the stream's callback,
        and updates the associated groups and clients.

        Args:
            data (dict): The data containing the stream update information.
        """
        if data.get("id") in self._streams:
            self._streams[data.get("id")].update(data.get("stream"))
            _LOGGER.debug(
                "stream %s updated", self._streams[data.get("id")].friendly_name
            )
            self._streams[data.get("id")].callback()
            for group in self._groups.values():
                if group.stream == data.get("id"):
                    group.callback()
                    for client_id in group.clients:
                        self._clients.get(client_id).callback()
        else:
            if (
                data.get("stream", {}).get("uri", {}).get("query", {}).get("codec")
                == "null"
            ):
                _LOGGER.debug("stream %s is input-only, ignore", data.get("id"))
            else:
                _LOGGER.info("stream %s not found, synchronize", data.get("id"))

                async def async_sync():
                    self.synchronize((await self.status())[0])

                asyncio.ensure_future(async_sync())

    def set_on_update_callback(self, func):
        """
        Set the on update callback function.

        Parameters:
        - func: The callback function to be set.
        """
        self._on_update_callback_func = func

    def set_on_connect_callback(self, func):
        """
        Set on connection callback function.

        Args:
            func: The function to be called when a connection is established.
        """
        self._on_connect_callback_func = func

    def set_on_disconnect_callback(self, func):
        """
        Set on disconnection callback function.

        Args:
            func: The function to be called when a connection is lost.
        """
        self._on_disconnect_callback_func = func

    def set_new_client_callback(self, func):
        """
        Set new client callback function.

        Parameters:
        - func: The callback function to be set.
        """
        self._new_client_callback_func = func

    def __repr__(self):
        """Return string representation of the Snapserver object."""
        return f"Snapserver {self.version} ({self._host})"

    def _version_check(self, api_call):
        """
        Checks if the server version meets the minimum requirement for a given API call.

        Args:
            api_call (str): The name of the API call.

        Raises:
            ServerVersionError: If the server version is lower than the required version for the API call.
        """
        if version.parse(self.version) < version.parse(_VERSIONS.get(api_call)):
            raise ServerVersionError(
                f"{api_call} requires server version >= {_VERSIONS[api_call]}."
                + f" Current version is {self.version}"
            )
