"""Tests for snapcast.control.protocol.SnapcastProtocol.

These tests cover the JSON-RPC ID allocation, response dispatch,
cancellation cleanup, and thread-safety contract.
"""
import asyncio
import json
import threading
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


class TestRequestIdThreadSafety(unittest.TestCase):
    """Bug A: request id allocation must be unique under concurrent multi-thread access.

    Why this test exists: SnapcastProtocol is currently used from a single asyncio
    thread, but the public API doesn't forbid asyncio.run_coroutine_threadsafe
    from multiple threads, and a future refactor may legitimately need cross-thread
    id allocation. If anyone switches the implementation to a non-thread-safe
    primitive (itertools.count without GIL guarantees, or naive `+= 1`), this test
    exposes it under contention. The test stays valid even under PEP 703
    free-threaded builds where GIL-based atomicity assumptions silently fail.
    """

    def test_request_id_thread_safety_under_high_concurrency(self):
        proto = make_protocol()
        num_threads = 32
        ids_per_thread = 1000
        all_ids: list[int] = []
        collect_lock = threading.Lock()

        def worker():
            local = [proto._next_request_id() for _ in range(ids_per_thread)]
            with collect_lock:
                all_ids.extend(local)

        threads = [threading.Thread(target=worker) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        expected = num_threads * ids_per_thread
        self.assertEqual(len(all_ids), expected)
        self.assertEqual(
            len(set(all_ids)),
            expected,
            f"Duplicate ids detected under thread contention: "
            f"{expected - len(set(all_ids))} collisions",
        )


class TestMalformedResponse(unittest.TestCase):
    """Bug A: handle_response must tolerate JSON-RPC responses without an id field."""

    def test_response_with_missing_id_field_no_crash(self):
        proto = make_protocol()
        # No id key at all -> .get('id') returns None -> _buffer.get(None) is None -> early return
        proto.handle_response({"result": {"foo": "bar"}})
        # Empty result key, no id -> still no crash
        proto.handle_response({})
        # The protocol stays usable
        self.assertEqual(proto._buffer, {})


if __name__ == "__main__":
    unittest.main()
