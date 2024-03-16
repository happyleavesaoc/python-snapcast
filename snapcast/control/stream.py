"""Snapcast stream."""


class Snapstream():
    """Represents a snapcast stream."""

    def __init__(self, data):
        """Initialize."""
        self.update(data)
        self._callback_func = None

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
    def metadata(self):
        """Get metadata."""
        if 'properties' in self._stream:
            return self._stream['properties'].get('metadata')
        return self._stream.get('meta')

    @property
    def meta(self):
        """Get metadata. Deprecated."""
        return self.metadata

    @property
    def properties(self):
        """Get properties."""
        return self._stream.get('properties')

    @property
    def path(self):
        """Get stream path."""
        return self._stream.get('uri').get('path')

    def update(self, data):
        """Update stream."""
        self._stream = data

    def update_meta(self, data):
        """Update stream metadata."""
        self.update_metadata(data)

    def update_metadata(self, data):
        """Update stream metadata."""
        if 'properties' in self._stream:
            self._stream['properties']['metadata'] = data
        self._stream['meta'] = data

    def update_properties(self, data):
        """Update stream properties."""
        self._stream['properties'] = data

    def __repr__(self):
        """Return string representation."""
        return f'Snapstream ({self.name})'

    def callback(self):
        """Run callback."""
        if self._callback_func and callable(self._callback_func):
            self._callback_func(self)

    def set_callback(self, func):
        """Set callback."""
        self._callback_func = func
