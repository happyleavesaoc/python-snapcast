"""Snapcast stream."""


class Snapstream(object):
    """Represents a snapcast stream."""

    def __init__(self, data):
        """Initialize."""
        self.update(data)
        self._new_metadata_callback_func = None

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

    def set_meta(self, tags):
        """Set stream metadata."""
        yield from self._server.stream_setmeta(self.identifier, tags)
        _LOGGER.info('set stream metadata on %s', self.identifier)

    def update_meta(self, data):
        """Update stream metadata."""
        self._stream["meta"] = data
        if self._new_metadata_callback_func and callable(self._new_metadata_callback_func):
            self._new_metadata_callback_func(self)

    def update(self, data):
        """Update stream."""
        self._stream = data

    def set_meta_callback(self, func):
        """Set new metadata callback function."""
        self._new_metadata_callback_func = func

    def __repr__(self):
        """String representation."""
        return 'Snapstream ({})'.format(self.name)
