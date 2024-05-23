"""Snapcast group."""
import logging

_LOGGER = logging.getLogger(__name__)

# pylint: disable=too-many-public-methods
class Snapgroup:
    """Represents a snapcast group.

    Attributes:
        _server (str): The server address.
        _snapshot (dict): The snapshot of the group's state.
        _callback_func (callable): The callback function for the group.
    """

    def __init__(self, server, data):
        """Initialize the group object.

        Args:
            server (str): The server address.
            data (dict): The initial data for the group.
        """
        self._server = server
        self._snapshot = None
        self._callback_func = None
        self.update(data)

    def update(self, data):
        """Update group data.

        Args:
            data (dict): The updated group data.
        """
        self._group = data

    @property
    def identifier(self):
        """Get group identifier.

        Returns:
            str: The identifier of the group.
        """
        return self._group.get('id')

    @property
    def name(self):
        """Get group name.

        Returns:
            str: The name of the group.
        """
        return self._group.get('name')

    async def set_name(self, name):
        """Set a group name.

        Args:
            name (str): The name to set for the group.
        """
        if not name:
            name = ''
        self._group['name'] = name
        await self._server.group_name(self.identifier, name)

    @property
    def stream(self):
        """Get stream identifier.

        Returns:
            str: The stream identifier of the group.
        """
        return self._group.get('stream_id')

    async def set_stream(self, stream_id):
        """Set group stream.

        Args:
            stream_id (str): The stream identifier to set for the group.
        """
        self._group['stream_id'] = stream_id
        await self._server.group_stream(self.identifier, stream_id)
        _LOGGER.debug('set stream to %s on %s', stream_id, self.friendly_name)

    @property
    def stream_status(self):
        """Get stream status.

        Returns:
            str: The status of the stream.
        """
        return self._server.stream(self.stream).status

    @property
    def muted(self):
        """Get mute status.

        Returns:
            bool: True if the group is muted, False otherwise.
        """
        return self._group.get('muted')

    async def set_muted(self, status):
        """Set group mute status.

        Args:
            status (bool): The mute status to set for the group.
        """
        self._group['muted'] = status
        await self._server.group_mute(self.identifier, status)
        _LOGGER.debug('set muted to %s on %s', status, self.friendly_name)

    @property
    def volume(self):
        """Get volume.

        Returns:
            int: The volume percent of the group.
        """
        volume_sum = 0
        for client in self._group.get('clients'):
            volume_sum += self._server.client(client.get('id')).volume
        return int(volume_sum / len(self._group.get('clients')))

    async def set_volume(self, volume):
        """Set volume.

        Args:
            volume (int): The volume percent to set for the group.

        Raises:
            ValueError: If volume percent is out of range.
        """
        if volume not in range(0, 101):
            raise ValueError('Volume out of range')
        current_volume = self.volume
        if volume == current_volume:
            _LOGGER.debug('left volume at %s on group %s', volume, self.friendly_name)
            return
        delta = volume - current_volume
        if delta < 0:
            ratio = (current_volume - volume) / current_volume
        else:
            ratio = (volume - current_volume) / (100 - current_volume)
        for data in self._group.get('clients'):
            client = self._server.client(data.get('id'))
            client_volume = client.volume
            if delta < 0:
                client_volume -= ratio * client_volume
            else:
                client_volume += ratio * (100 - client_volume)
            client_volume = round(client_volume)
            await client.set_volume(client_volume, update_group=False)
            client.update_volume({
                'volume': {
                    'percent': client_volume,
                    'muted': client.muted
                }
            })
        _LOGGER.debug('set volume to %s on group %s', volume, self.friendly_name)

    @property
    def friendly_name(self):
        """Get friendly name.

        Returns:
            str: The friendly name of the group.
        """
        fname = self.name if self.name != '' else "+".join(
            sorted([self._server.client(c).friendly_name for c in self.clients
                    if c in [client.identifier for client in self._server.clients]]))
        return fname if fname != '' else self.identifier

    @property
    def clients(self):
        """Get client identifiers.

        Returns:
            list: The list of client identifiers in the group.
        """
        return [client.get('id') for client in self._group.get('clients')]

    async def add_client(self, client_identifier):
        """Add a client to the group.

        Args:
            client_identifier (str): The identifier of the client to add.
        """
        if client_identifier in self.clients:
            _LOGGER.error('%s already in group %s', client_identifier, self.identifier)
            return
        new_clients = self.clients
        new_clients.append(client_identifier)
        await self._server.group_clients(self.identifier, new_clients)
        _LOGGER.debug('added %s to %s', client_identifier, self.identifier)
        status = (await self._server.status())[0]
        self._server.synchronize(status)
        self._server.client(client_identifier).callback()
        self.callback()

    async def remove_client(self, client_identifier):
        """Remove a client from the group.

        Args:
            client_identifier (str): The identifier of the client to remove.
        """
        new_clients = self.clients
        new_clients.remove(client_identifier)
        await self._server.group_clients(self.identifier, new_clients)
        _LOGGER.debug('removed %s from %s', client_identifier, self.identifier)
        status = (await self._server.status())[0]
        self._server.synchronize(status)
        self._server.client(client_identifier).callback()
        self.callback()

    def streams_by_name(self):
        """Get available stream objects by name.

        Returns:
            dict: A dictionary of stream objects keyed by their friendly names.
        """
        return {stream.friendly_name: stream for stream in self._server.streams}

    def update_mute(self, data):
        """Update mute status.

        Args:
            data (dict): The updated mute data.
        """
        self._group['muted'] = data['mute']
        self.callback()
        _LOGGER.debug('updated mute on %s', self.friendly_name)

    def update_name(self, data):
        """Update group name.

        Args:
            data (dict): The updated name data.
        """
        self._group['name'] = data['name']
        _LOGGER.debug('updated name on %s', self.name)
        self.callback()

    def update_stream(self, data):
        """Update stream.

        Args:
            data (dict): The updated stream data.
        """
        self._group['stream_id'] = data['stream_id']
        self.callback()
        _LOGGER.debug('updated stream to %s on %s', self.stream, self.friendly_name)

    def snapshot(self):
        """Take a snapshot of the current state."""
        self._snapshot = {
            'muted': self.muted,
            'volume': self.volume,
            'stream': self.stream
        }
        _LOGGER.debug('took snapshot of current state of %s', self.friendly_name)

    async def restore(self):
        """Restore the snapshotted state."""
        if not self._snapshot:
            return
        await self.set_muted(self._snapshot['muted'])
        await self.set_volume(self._snapshot['volume'])
        await self.set_stream(self._snapshot['stream'])
        self.callback()
        _LOGGER.debug('restored snapshot of state of %s', self.friendly_name)

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
        """Return string representation of the group.

        Returns:
            str: The string representation of the group.
        """
        return f'Snapgroup ({self.friendly_name}, {self.identifier})'