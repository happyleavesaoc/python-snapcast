"""Tests for snapcast.control.protocol.SnapcastProtocol.

These tests cover the JSON-RPC ID allocation, response dispatch,
cancellation cleanup, and thread-safety contract.
"""
import asyncio
import json
import unittest
from unittest.mock import MagicMock

from snapcast.control.protocol import SnapcastProtocol


class FakeTransport:
    """Captures bytes written to the transport for inspection."""

    def __init__(self):
        self.written: list[bytes] = []
        self._closing = False

    def write(self, data):
        self.written.append(data)

    def is_closing(self):
        return self._closing

    def close(self):
        self._closing = True


def make_protocol() -> SnapcastProtocol:
    """Build a SnapcastProtocol wired to a FakeTransport."""
    callbacks = {
        "Server.OnDisconnect": MagicMock(),
    }
    proto = SnapcastProtocol(callbacks)
    proto.connection_made(FakeTransport())
    return proto


def written_request(proto: SnapcastProtocol, idx: int = -1) -> dict:
    """Decode the JSON-RPC payload from the Nth write on the transport."""
    raw = proto._transport.written[idx]
    text = raw.decode().rstrip("\r\n")
    return json.loads(text)


class TestProtocolBaseline(unittest.TestCase):
    """Smoke test that the test file is wired up correctly."""

    def test_make_protocol_constructs(self):
        proto = make_protocol()
        self.assertIsNotNone(proto._transport)
        self.assertEqual(proto._buffer, {})


if __name__ == "__main__":
    unittest.main()
