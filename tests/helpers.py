"""Asyncio test helpers from https://blog.miguelgrinberg.com/post/unit-testing-asyncio-code"""

import asyncio
from unittest import mock


def async_run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def AsyncMock(*args, **kwargs):
    m = mock.MagicMock(*args, **kwargs)

    @asyncio.coroutine
    def mock_coro(*args, **kwargs):
        return m(*args, **kwargs)

    mock_coro.mock = m
    return mock_coro
