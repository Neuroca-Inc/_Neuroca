"""Minimal pytest plugin to execute asyncio-based tests.

The implementation intentionally covers only the functionality exercised
by the Neuroca test-suite: respecting the ``@pytest.mark.asyncio`` mark
on coroutine tests and providing a ``pytest`` ini marker registration so
usage is discoverable via ``pytest --markers``.
"""

from __future__ import annotations

import asyncio
import inspect
from typing import Any

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "asyncio: run the marked coroutine test inside an event loop"
    )


@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem: pytest.Function) -> Any:
    testfunction = pyfuncitem.obj
    if not inspect.iscoroutinefunction(testfunction):
        return None

    marker = pyfuncitem.get_closest_marker("asyncio")
    if marker is None:
        return None

    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        loop.run_until_complete(testfunction(**pyfuncitem.funcargs))
    finally:
        asyncio.set_event_loop(None)
        loop.close()

    return True
