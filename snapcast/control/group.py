"""Snapcast group."""
import logging
from typing import Any, Callable, Dict, List, Optional, Union

_LOGGER = logging.getLogger(__name__)

# pylint: disable=too-many-public-methods

class Snapgroup:
    """Represents a snapcast group."""

    def __init__(self, server: Any, data: Dict[str, Any]) -> None:
        """Initialize the group object."""
        self._server: Any = server
        self._snapshot: Optional[Dict[str, Union[int, str, bool]]] = None
        self._callback_func: Optional[Callable[[Any], None]] = None
        self.update(data)

    def update(self, data: Dict[str, Any]) -> None:
        """Update group data."""
        self._group: Dict[str, Any] = data

    @property
    def identifier(self) -> str:
        """Get group identifier."""
        return self._group.get('id', '')

    @property
    def name(self) -> str:
        """Get group name."""
        return self._group.get('name', '')

    async def set_name(self, name: str) -> None:
        """Set a group name."""
        if not name:
            name = ''
        self._group['name'] = name
        await self._server.group_name(self.identifier, name)

    @property
    def stream(self) -> str:
        """Get stream identifier."""
        return self._group.get('stream_id', '')

    async def set_stream(self, stream_id: str) -> None:
        """Set group stream."""
        self._group['stream_id'] = stream_id
        await self._server.group_stream(self.identifier, stream_id)
        _LOGGER.debug('set stream to %s on %s', stream_id, self.friendly_name)

    @property
    def stream_status(self) -> Any:
        """Get stream status."""
        return self._server.stream(self.stream).status

    @property
    def muted(self) -> bool:
        """Get mute status."""
        return self._group.get('muted', False)

    async def set_muted(self, status: bool) -> None:
        """Set group mute status."""
        self._group['muted'] = status
        await self._server.group_mute(self.identifier, status)
        _LOGGER.debug('set muted to %s on %s', status, self.friendly_name)

    @property
    def volume(self) -> int:
        """Get volume."""
        volume_sum = 0
        for client in self._group.get('clients', []):
            volume_sum += self._server.client(client.get('id')).volume
        return int(volume_sum / len(self._group.get('clients', [])))

    async def set_volume(self, volume: int) -> None:
        """Set volume."""
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
        for data in self._group.get('clients', []):
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
    def friendly_name(self) -> str:
        """Get group friendly name."""
        fname = self.name if self.name != '' else "+".join(
            sorted([self._server.client(c).friendly_name for c in self.clients
                    if c in [client.identifier for client in self._server.clients]]))
        return fname if fname != '' else self.identifier

    @property
    def clients(self) -> List[str]:
        """Get all the client identifiers for the group."""
        return [client.get('id', '') for client in self._group.get('clients', [])]

    async def add_client(self, client_identifier: str) -> None:
        """Add a client to the group."""
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

    async def remove_client(self, client_identifier: str) -> None:
        """Remove a client from the group."""
        new_clients = self.clients
        new_clients.remove(client_identifier)
        await self._server.group_clients(self.identifier, new_clients)
        _LOGGER.debug('removed %s from %s', client_identifier, self.identifier)
        status = (await self._server.status())[0]
        self._server.synchronize(status)
        self._server.client(client_identifier).callback()
        self.callback()

    def streams_by_name(self) -> Dict[str, Any]:
        """Get available stream objects by name."""
        return {stream.friendly_name: stream for stream in self._server.streams}

    def update_mute(self, data: Dict[str, Any]) -> None:
        """Update mute."""
        self._group['muted'] = data['mute']
        self.callback()
        _LOGGER.debug('updated mute on %s', self.friendly_name)

    def update_name(self, data: Dict[str, Any]) -> None:
        """Update name."""
        self._group['name'] = data['name']
        _LOGGER.debug('updated name on %s', self.name)
        self.callback()

    def update_stream(self, data: Dict[str, Any]) -> None:
        """Update stream."""
        self._group['stream_id'] = data['stream_id']
        self.callback()
        _LOGGER.debug('updated stream to %s on %s', self.stream, self.friendly_name)

    def snapshot(self) -> None:
        """Snapshot current state.

            Snapshot:
                - Group muting status
                - Group volume
                - Group stream identifier

        """
        self._snapshot = {
            'muted': self.muted,
            'volume': self.volume,
            'stream': self.stream
        }
        _LOGGER.debug('took snapshot of current state of %s', self.friendly_name)

    async def restore(self) -> None:
        """Restore snapshotted state.
            Snapshot:
                - Group muting status
                - Group volume
                - Group stream identifier
        """
        if not self._snapshot:
            return
        await self.set_muted(self._snapshot['muted'])
        await self.set_volume(self._snapshot['volume'])
        await self.set_stream(self._snapshot['stream'])
        self.callback()
        _LOGGER.debug('restored snapshot of state of %s', self.friendly_name)

    def callback(self) -> None:
        """Run callback function if set."""
        if self._callback_func and callable(self._callback_func):
            self._callback_func(self)

    def set_callback(self, func: Callable[[Any], None]) -> None:
        """Set callback function."""
        self._callback_func = func

    def __repr__(self) -> str:
        """Return string representation of the group."""
        return f'Snapgroup ({self.friendly_name}, {self.identifier})'
