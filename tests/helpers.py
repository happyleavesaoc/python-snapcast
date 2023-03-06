"""Asyncio test helpers from https://blog.miguelgrinberg.com/post/unit-testing-asyncio-code"""

import asyncio


def async_run(coro):
    return asyncio.run(coro)
