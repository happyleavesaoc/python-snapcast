"""Snapcast client."""
import asyncio
import logging


_LOGGER = logging.getLogger(__name__)


# pylint: disable=too-many-public-methods
class Snapclient(object):
    """Represents a snapclient."""

    def __init__(self, server, data):
        """Initialize."""
        self._server = server
        self._snapshot = None
        self._last_seen = None
        self._callback_func = None
        self._client = data

    @property
    def identifier(self):
        """Get identifier."""
        return self._client.get('id')

    @property
    def group(self):
        """Get group."""
        for group in self._server.groups:
            if self.identifier in group.clients:
                return group

    @property
    def friendly_name(self):
        """Get friendly name."""
        if len(self._client.get('config').get('name')):
            return self._client.get('config').get('name')
        return self._client.get('host').get('name')

    @property
    def version(self):
        """Version."""
        return self._client.get('snapclient').get('version')

    @property
    def connected(self):
        """Connected or not."""
        return self._client.get('connected')

    @property
    def name(self):
        """Name."""
        return self._client.get('config').get('name')

    @asyncio.coroutine
    def set_name(self, name):
        """Set a client name."""
        if not name:
            name = ''
        self._client['config']['name'] = name
        yield from self._server.client_name(self.identifier, name)

    @property
    def latency(self):
        """Latency."""
        return self._client.get('config').get('latency')

    @asyncio.coroutine
    def set_latency(self, latency):
        """Set client latency."""
        self._client['config']['latency'] = latency
        yield from self._server.client_latency(self.identifier, latency)

    @property
    def muted(self):
        """Muted or not."""
        return self._client.get('config').get('volume').get('muted')

    @asyncio.coroutine
    def set_muted(self, status):
        """Set client mute status."""
        new_volume = self._client['config']['volume']
        new_volume['muted'] = status
        self._client['config']['volume']['muted'] = status
        yield from self._server.client_volume(self.identifier, new_volume)
        _LOGGER.info('set muted to %s on %s', status, self.friendly_name)

    @property
    def volume(self):
        """Volume percent."""
        return self._client.get('config').get('volume').get('percent')

    @asyncio.coroutine
    def set_volume(self, percent, update_group=True):
        """Set client volume percent."""
        if percent not in range(0, 101):
            raise ValueError('Volume percent out of range')
        new_volume = self._client['config']['volume']
        new_volume['percent'] = percent
        self._client['config']['volume']['percent'] = percent
        yield from self._server.client_volume(self.identifier, new_volume)
        if update_group:
            self._server.group(self.group.identifier).callback()
        _LOGGER.info('set volume to %s on %s', percent, self.friendly_name)

    def groups_available(self):
        """Get available group objects."""
        return [group for group in self._server.groups]

    def update_volume(self, data):
        """Update volume."""
        self._client['config']['volume'] = data['volume']
        _LOGGER.info('updated volume on %s', self.friendly_name)
        self._server.group(self.group.identifier).callback()
        self.callback()

    def update_name(self, data):
        """Update name."""
        self._client['config']['name'] = data['name']
        _LOGGER.info('updated name on %s', self.friendly_name)
        self.callback()

    def update_latency(self, data):
        """Update latency."""
        self._client['config']['latency'] = data['latency']
        _LOGGER.info('updated latency on %s', self.friendly_name)
        self.callback()

    def update_connected(self, status):
        """Update connected."""
        self._client['connected'] = status
        _LOGGER.info('updated connected status to %s on %s', status, self.friendly_name)
        self.callback()

    def snapshot(self):
        """Snapshot current state."""
        self._snapshot = {
            'name': self.name,
            'volume': self.volume,
            'muted': self.muted,
            'latency': self.latency
        }
        _LOGGER.info('took snapshot of current state of %s', self.friendly_name)

    @asyncio.coroutine
    def restore(self):
        """Restore snapshotted state."""
        if not self._snapshot:
            return
        yield from self.set_name(self._snapshot['name'])
        yield from self.set_volume(self._snapshot['volume'])
        yield from self.set_muted(self._snapshot['muted'])
        yield from self.set_latency(self._snapshot['latency'])
        self.callback()
        _LOGGER.info('restored snapshot of state of %s', self.friendly_name)

    def callback(self):
        """Run callback."""
        if self._callback_func and callable(self._callback_func):
            self._callback_func(self)

    def set_callback(self, func):
        """Set callback function."""
        self._callback_func = func

    def __repr__(self):
        """String representation."""
        return 'Snapclient {} ({}, {})'.format(
            self.version, self.friendly_name, self.identifier)
