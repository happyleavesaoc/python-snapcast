"""Snapcast control for Snapcast 0.11.1."""

from snapcast.control.server import Snapserver, CONTROL_PORT
from snapcast.control.client import Snapclient
from snapcast.control.stream import Snapstream
from snapcast.control.group import Snapgroup


async def create_server(loop, host, port=CONTROL_PORT, reconnect=False):
    """Server factory."""
    server = Snapserver(loop, host, port, reconnect)
    await server.start()
    return server
