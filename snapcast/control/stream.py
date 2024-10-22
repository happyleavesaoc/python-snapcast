"""Snapcast stream."""
from typing import Any, Callable, Optional


class Snapstream:
    """Represents a snapcast stream."""

    def __init__(self, data: dict) -> None:
        """Initialize the Stream object."""
        self.update(data)
        self._callback_func: Optional[Callable[['Snapstream'], None]] = None

    @property
    def identifier(self) -> str:
        """Get stream id."""
        return self._stream.get('id')

    @property
    def status(self) -> Any:
        """Get stream status."""
        return self._stream.get('status')

    @property
    def name(self) -> str:
        """Get stream name."""
        return self._stream.get('uri', {}).get('query', {}).get('name', '')

    @property
    def friendly_name(self) -> str:
        """Get friendly name."""
        return self.name if self.name != '' else self.identifier

    @property
    def metadata(self) -> Optional[dict]:
        """Get metadata."""
        if 'properties' in self._stream:
            return self._stream['properties'].get('metadata')
        return self._stream.get('meta')

    @property
    def meta(self) -> Optional[dict]:
        """Get metadata. Deprecated."""
        return self.metadata

    @property
    def properties(self) -> Optional[dict]:
        """Get properties."""
        return self._stream.get('properties')

    @property
    def path(self) -> str:
        """Get stream path."""
        return self._stream.get('uri', {}).get('path', '')

    def update(self, data: dict) -> None:
        """Update stream."""
        self._stream = data

    def update_meta(self, data: dict) -> None:
        """Update stream metadata."""
        self.update_metadata(data)

    def update_metadata(self, data: dict) -> None:
        """Update stream metadata."""
        if 'properties' in self._stream:
            self._stream['properties']['metadata'] = data
        self._stream['meta'] = data

    def update_properties(self, data: dict) -> None:
        """Update stream properties."""
        self._stream['properties'] = data

    def __repr__(self) -> str:
        """Return string representation."""
        return f'Snapstream ({self.name})'

    def callback(self) -> None:
        """Run callback if set."""
        if self._callback_func and callable(self._callback_func):
            self._callback_func(self)

    def set_callback(self, func: Callable[['Snapstream'], None]) -> None:
        """Set callback function."""
        self._callback_func = func
