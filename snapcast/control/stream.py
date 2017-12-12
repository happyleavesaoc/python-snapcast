"""Snapcast stream."""


class Snapstream(object):
    """Represents a snapcast stream."""

    def __init__(self, data):
        """Initialize."""
        self.update(data)

    @property
    def identifier(self):
        """Get stream id."""
        return self._stream.get('id')

    @property
    def status(self):
        """Get stream status."""
        return self._stream.get('status')

    @property
    def name(self):
        """Get stream name."""
        return self._stream.get('uri').get('query').get('name')

    @property
    def friendly_name(self):
        """Get friendly name."""
        return self.name if self.name != '' else self.identifier

    @property
    def meta(self):
        """Get metadata."""
        return self._stream.get('meta')

    def update(self, data):
        """Update stream."""
        self._stream = data

    def __repr__(self):
        """String representation."""
        return 'Snapstream ({})'.format(self.name)
