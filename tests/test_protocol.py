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


class TestHandleResponse(unittest.TestCase):
    """Bug A: handle_response must not raise for unknown/orphan request ids."""

    def test_handle_response_for_unknown_id_does_not_raise(self):
        proto = make_protocol()
        # No request was made, so buffer is empty
        self.assertEqual(proto._buffer, {})
        # Server sends a response with an id we don't know about
        proto.handle_response({"id": 999, "result": {"server": {}}})
        # Should be a no-op, not a KeyError
        self.assertEqual(proto._buffer, {})


class TestRequestCancellation(unittest.TestCase):
    """Bug A: cancelling an in-flight request() must always clean its buffer entry."""

    def test_request_cancellation_cleans_buffer(self):
        async def run():
            proto = make_protocol()
            task = asyncio.create_task(proto.request("Server.GetStatus", {}))
            # Yield control so request() runs up to flag.wait()
            await asyncio.sleep(0)
            # Buffer should now hold one pending entry
            self.assertEqual(len(proto._buffer), 1)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            # After cancellation the buffer must be empty again
            self.assertEqual(proto._buffer, {})

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
