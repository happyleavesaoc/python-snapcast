"""Errors raised by high-level Snapcast operations."""


class SnapcastRequestError(Exception):
    """A JSON-RPC request rejected by Snapserver.

    The low-level transaction API still returns (result, error). High-level
    operations use this exception when silently ignoring an error would leave
    their cached state inconsistent with the server.
    """

    def __init__(self, method, error):
        self.method = method
        self.error = error
        self.code = error.get('code')
        super().__init__('{} failed: {} ({})'.format(
            method, error.get('data') or error.get('message'), self.code))
