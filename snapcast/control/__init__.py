"""Snapcast control for Snapcast 0.11.1."""

from snapcast.control.server import Snapserver, CONTROL_PORT


async def create_server(loop, host, port=CONTROL_PORT, reconnect=False, use_websockets=False):
    """Server factory."""
    server = Snapserver(loop, host, port, reconnect, use_websockets)
    await server.start()
    return server
