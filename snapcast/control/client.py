"""Snapcast client."""
import logging
from typing import Any, Callable, Dict, List, Optional, Union

_LOGGER = logging.getLogger(__name__)


# pylint: disable=too-many-public-methods
class Snapclient:
    """Initialize the Client object."""

    def __init__(self, server: Any, data: Dict[str, Any]) -> None:
        """Initialize."""
        self._server = server
        self._snapshot: Optional[Dict[str, Union[str, int, bool]]] = None
        self._last_seen: Optional[str] = None
        self._callback_func: Optional[Callable[[Any], None]] = None
        self.update(data)

    def update(self, data: Dict[str, Any]) -> None:
        """Update client."""
        self._client = data

    @property
    def identifier(self) -> Optional[str]:
        """Get client identifier."""
        return self._client.get('id')

    @property
    def group(self) -> Optional[Any]:
        """Get group that the client is part of"""
        for group in self._server.groups:
            if self.identifier in group.clients:
                return group
        return None

    @property
    def friendly_name(self) -> str:
        """Get client friendly name."""
        if len(self._client.get('config', {}).get('name', '')):
            return self._client.get('config').get('name', '')
        return self._client.get('host', {}).get('name', '')

    @property
    def version(self) -> Optional[str]:
        """Get client snapclient version."""
        return self._client.get('snapclient', {}).get('version')

    @property
    def connected(self) -> bool:
        """Get the current connection status of the client."""
        return self._client.get('connected', False)

    @property
    def name(self) -> str:
        """Get name of the client."""
        return self._client.get('config', {}).get('name', '')

    async def set_name(self, name: str) -> None:
        """Set a new name for the client."""
        if not name:
            name = ''
        self._client['config']['name'] = name
        await self._server.client_name(self.identifier, name)

    @property
    def latency(self) -> Optional[int]:
        """Get client latency."""
        return self._client.get('config', {}).get('latency')

    async def set_latency(self, latency: int) -> None:
        """Set client latency."""
        self._client['config']['latency'] = latency
        await self._server.client_latency(self.identifier, latency)

    @property
    def muted(self) -> bool:
        """Muted or not."""
        return self._client.get('config', {}).get('volume', {}).get('muted', False)

    async def set_muted(self, status: bool) -> None:
        """Set client mute status."""
        new_volume = self._client['config']['volume']
        new_volume['muted'] = status
        self._client['config']['volume']['muted'] = status
        await self._server.client_volume(self.identifier, new_volume)
        _LOGGER.debug('set muted to %s on %s', status, self.friendly_name)

    @property
    def volume(self) -> int:
        """Get client volume percent."""
        return self._client.get('config', {}).get('volume', {}).get('percent', 0)

    async def set_volume(self, percent: int, update_group: bool = True) -> None:
        """Set client volume percent."""
        if percent not in range(0, 101):
            raise ValueError('Volume percent out of range')
        new_volume = self._client['config']['volume']
        new_volume['percent'] = percent
        self._client['config']['volume']['percent'] = percent
        await self._server.client_volume(self.identifier, new_volume)
        if update_group:
            self._server.group(self.group.identifier).callback()
        _LOGGER.debug('set volume to %s on %s', percent, self.friendly_name)

    def groups_available(self) -> List[Any]:
        """Get available group objects."""
        return list(self._server.groups)

    def update_volume(self, data: Dict[str, Any]) -> None:
        """Update volume."""
        self._client['config']['volume'] = data['volume']
        _LOGGER.debug('updated volume on %s', self.friendly_name)
        self._server.group(self.group.identifier).callback()
        self.callback()

    def update_name(self, data: Dict[str, Any]) -> None:
        """Update name."""
        self._client['config']['name'] = data['name']
        _LOGGER.debug('updated name on %s', self.friendly_name)
        self.callback()

    def update_latency(self, data: Dict[str, Any]) -> None:
        """Update latency."""
        self._client['config']['latency'] = data['latency']
        _LOGGER.debug('updated latency on %s', self.friendly_name)
        self.callback()

    def update_connected(self, status: bool) -> None:
        """Update connected."""
        self._client['connected'] = status
        _LOGGER.debug('updated connected status to %s on %s', status, self.friendly_name)
        self.callback()

    def snapshot(self) -> None:
        """Snapshot current state of the client.
        
            Snapshot:
                - Client name
                - Client volume
                - Client muting status
                - Client latency
        """
        self._snapshot = {
            'name': self.name,
            'volume': self.volume,
            'muted': self.muted,
            'latency': self.latency
        }
        _LOGGER.debug('took snapshot of current state of %s', self.friendly_name)

    async def restore(self) -> None:
        """Restore snapshotted state.
            Snapshot:
                - Client name
                - Client volume
                - Client muting status
                - Client latency
        """
        if not self._snapshot:
            return
        await self.set_name(self._snapshot['name'])
        await self.set_volume(self._snapshot['volume'])
        await self.set_muted(self._snapshot['muted'])
        await self.set_latency(self._snapshot['latency'])
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
        """Return string representation of the client."""
        return f'Snapclient {self.version} ({self.friendly_name}, {self.identifier})'
