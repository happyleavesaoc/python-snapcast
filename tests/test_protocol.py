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


class TestConcurrentAsyncRequests(unittest.TestCase):
    """Bug A: multiple concurrent asyncio request() calls must each get a unique id."""

    def test_concurrent_async_requests_get_distinct_ids(self):
        async def run():
            proto = make_protocol()

            async def issue():
                # Start request, but don't wait for the (never-coming) response
                t = asyncio.create_task(proto.request("Server.GetStatus", {}))
                await asyncio.sleep(0)
                return t

            tasks = [await issue() for _ in range(200)]
            try:
                ids = []
                for raw in proto._transport.written:
                    payload = json.loads(raw.decode().rstrip("\r\n"))
                    ids.append(payload["id"])
                self.assertEqual(len(ids), 200)
                self.assertEqual(len(set(ids)), 200)
            finally:
                for t in tasks:
                    t.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)

        asyncio.run(run())


class TestNoCollisionCorruption(unittest.TestCase):
    """Bug A end-to-end: each request must get its own response back, never another's."""

    def test_no_collision_corruption_under_load(self):
        async def run():
            proto = make_protocol()
            num = 100

            async def one_request(payload_marker):
                # Issue the request, then synthesize a matching response
                t = asyncio.create_task(proto.request("Server.GetStatus", {}))
                await asyncio.sleep(0)
                # Look up the id we just allocated
                last_payload = json.loads(
                    proto._transport.written[-1].decode().rstrip("\r\n")
                )
                req_id = last_payload["id"]
                # Server replies with our marker as the result
                proto.handle_response({"id": req_id, "result": {"marker": payload_marker}})
                result, error = await t
                return payload_marker, result, error

            answers = await asyncio.gather(
                *(one_request(i) for i in range(num))
            )
            for marker, result, error in answers:
                self.assertIsNone(error)
                self.assertEqual(result, {"marker": marker})

        asyncio.run(run())


class TestExistingBehaviorRegression(unittest.TestCase):
    """Confirm prior behavior of SnapcastProtocol is preserved by the Bug A fixes."""

    def test_happy_path_response_dispatch(self):
        async def run():
            proto = make_protocol()
            t = asyncio.create_task(proto.request("Server.GetStatus", {}))
            await asyncio.sleep(0)
            req_id = json.loads(proto._transport.written[-1].decode().rstrip("\r\n"))["id"]
            proto.handle_response({"id": req_id, "result": {"server": "ok"}})
            result, error = await t
            self.assertEqual(result, {"server": "ok"})
            self.assertIsNone(error)

        asyncio.run(run())

    def test_connection_lost_signals_all_pending(self):
        async def run():
            proto = make_protocol()
            t1 = asyncio.create_task(proto.request("A", {}))
            t2 = asyncio.create_task(proto.request("B", {}))
            await asyncio.sleep(0)
            self.assertEqual(len(proto._buffer), 2)
            proto.connection_lost(None)
            r1, e1 = await t1
            r2, e2 = await t2
            self.assertIsNone(r1)
            self.assertIsNone(r2)
            self.assertEqual(e1, {"code": -1, "message": "connection lost"})
            self.assertEqual(e2, {"code": -1, "message": "connection lost"})

        asyncio.run(run())

    def test_data_received_handles_partial_messages(self):
        proto = make_protocol()
        # Make a request first so the buffer has an entry to satisfy
        async def run():
            t = asyncio.create_task(proto.request("Server.GetStatus", {}))
            await asyncio.sleep(0)
            req_id = json.loads(proto._transport.written[-1].decode().rstrip("\r\n"))["id"]
            full = json.dumps({"id": req_id, "result": {"ok": True}}) + "\r\n"
            half_a = full[: len(full) // 2].encode()
            half_b = full[len(full) // 2 :].encode()
            proto.data_received(half_a)
            # Buffer is incomplete (no \r\n yet) -> request still pending
            self.assertEqual(len(proto._buffer), 1)
            proto.data_received(half_b)
            result, _ = await t
            self.assertEqual(result, {"ok": True})

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
