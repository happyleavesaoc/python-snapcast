"""Snapcast client."""

import logging

_LOGGER = logging.getLogger(__name__)


# pylint: disable=too-many-public-methods
class Snapclient:
    """Represents a snapclient.

    Attributes:
        _server (str): The server address.
        _snapshot (dict): The snapshot of the client's state.
        _last_seen: The last seen timestamp of the client.
        _callback_func: The callback function for the client.

    """

    def __init__(self, server, data):
        """Initialize the Client object.

        Args:
            server (str): The server address.
            data (dict): The initial data for the client.

        """
        self._server = server
        self._snapshot = None
        self._last_seen = None
        self._callback_func = None
        self.update(data)

    def update(self, data):
        """Update client.

        Args:
            data: The updated client data.

        """
        self._client = data

    @property
    def identifier(self):
        """Get identifier.

        Returns:
            The identifier of the client.
        """
        return self._client.get("id")

    @property
    def group(self):
        """Get the group that this client belongs to.

        Returns:
            The group object that this client belongs to, or None if the client is not in any group.
        """
        for group in self._server.groups:
            if self.identifier in group.clients:
                return group
        return None

    @property
    def friendly_name(self):
        """Get the friendly name of the client.

        Returns:
            str: The friendly name of the client.

        """
        if len(self._client.get("config").get("name")):
            return self._client.get("config").get("name")
        return self._client.get("host").get("name")

    @property
    def version(self):
        """Version.

        Returns:
            str: The version of the snapclient.
        """
        return self._client.get("snapclient").get("version")

    @property
    def connected(self):
        """Get the current connection status of the client.

        Returns:
            bool: True if the client is connected, False otherwise.
        """
        return self._client.get("connected")

    @property
    def name(self):
        """Get the name of the client.

        Returns:
            str: The name of the client.
        """
        return self._client.get("config").get("name")

    async def set_name(self, name):
        """Set a client name.

        Args:
            name (str): The name to set for the client.

        """
        if not name:
            name = ""
        self._client["config"]["name"] = name
        await self._server.client_name(self.identifier, name)

    @property
    def latency(self):
        """Get the client latency.

        Returns:
            int: The latency of the client.
        """
        return self._client.get("config").get("latency")

    async def set_latency(self, latency):
        """Set client latency.

        Args:
            latency (int): The latency to set for the client.
        """
        self._client["config"]["latency"] = latency
        await self._server.client_latency(self.identifier, latency)

    @property
    def muted(self):
        """Get the mute status of the client.

        Returns:
            bool: True if the client is muted, False otherwise.
        """
        return self._client.get("config").get("volume").get("muted")

    async def set_muted(self, status):
        """Set client mute status.

        Args:
            status (bool): The mute status to set for the client.
        """
        new_volume = self._client["config"]["volume"]
        new_volume["muted"] = status
        self._client["config"]["volume"]["muted"] = status
        await self._server.client_volume(self.identifier, new_volume)
        _LOGGER.debug("set muted to %s on %s", status, self.friendly_name)

    @property
    def volume(self):
        """Get the volume percent.

        Returns:
            int: The volume percent of the client.
        """
        return self._client.get("config").get("volume").get("percent")

    async def set_volume(self, percent, update_group=True):
        """Set client volume percent.

        Args:
            percent (int): The volume percent to set for the client.
            update_group (bool): Whether to update the group volume. Defaults to True.

        Raises:
            ValueError: If volume percent is out of range.
        """
        if percent not in range(0, 101):
            raise ValueError("Volume percent out of range")
        new_volume = self._client["config"]["volume"]
        new_volume["percent"] = percent
        self._client["config"]["volume"]["percent"] = percent
        await self._server.client_volume(self.identifier, new_volume)
        if update_group:
            self._server.group(self.group.identifier).callback()
        _LOGGER.debug("set volume to %s on %s", percent, self.friendly_name)

    def groups_available(self):
        """Get available group objects.

        Returns:
            list: The list of available group objects.
        """
        return list(self._server.groups)

    def update_volume(self, data):
        """Update volume.

        Args:
            data (dict): The updated volume data.
        """
        self._client["config"]["volume"] = data["volume"]
        _LOGGER.debug("updated volume on %s", self.friendly_name)
        self._server.group(self.group.identifier).callback()
        self.callback()

    def update_name(self, data):
        """Update name.

        Args:
            data (dict): The updated name data.
        """
        self._client["config"]["name"] = data["name"]
        _LOGGER.debug("updated name on %s", self.friendly_name)
        self.callback()

    def update_latency(self, data):
        """Update latency.

        Args:
            data (dict): The updated latency data.
        """
        self._client["config"]["latency"] = data["latency"]
        _LOGGER.debug("updated latency on %s", self.friendly_name)
        self.callback()

    def update_connected(self, status):
        """Update connected status.

        Args:
            status (bool): The new connected status.
        """
        self._client["connected"] = status
        _LOGGER.debug(
            "updated connected status to %s on %s", status, self.friendly_name
        )
        self.callback()

    def snapshot(self):
        """Take a snapshot of the current state."""
        self._snapshot = {
            "name": self.name,
            "volume": self.volume,
            "muted": self.muted,
            "latency": self.latency,
        }
        _LOGGER.debug("took snapshot of current state of %s", self.friendly_name)

    async def restore(self):
        """Restore the snapshotted state."""
        if not self._snapshot:
            return
        await self.set_name(self._snapshot["name"])
        await self.set_volume(self._snapshot["volume"])
        await self.set_muted(self._snapshot["muted"])
        await self.set_latency(self._snapshot["latency"])
        self.callback()
        _LOGGER.debug("restored snapshot of state of %s", self.friendly_name)

    def callback(self):
        """Run the callback function if set."""
        if self._callback_func and callable(self._callback_func):
            self._callback_func(self)

    def set_callback(self, func):
        """Set the callback function.

        Args:
            func (callable): The callback function to set.
        """
        self._callback_func = func

    def __repr__(self):
        """Return string representation of the client.

        Returns:
            str: The string representation of the client.
        """
        return f"Snapclient {self.version} ({self.friendly_name}, {self.identifier})"