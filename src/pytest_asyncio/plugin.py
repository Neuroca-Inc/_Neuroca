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
    """Execute async test functions inside a dedicated event loop.

    The default pytest implementation filters fixtures so that only the
    arguments requested by the test function are provided. The custom
    ``pytest_asyncio`` hook originally forwarded the complete ``funcargs``
    mapping, which broke when third-party plugins (for example,
    ``pytest-faker``) registered additional fixtures. The extra fixtures were
    passed as unexpected keyword arguments to async tests, raising ``TypeError``.

    To restore compatibility we mirror pytest's filtering behaviour by passing
    only the arguments declared on the async test function unless it accepts
    ``**kwargs``. When a coroutine test lacks the ``@pytest.mark.asyncio``
    marker, the hook still executes it inside an event loop (unless AnyIO is
    orchestrating execution) so legacy tests without explicit markers continue
    to run.
    """

    testfunction = pyfuncitem.obj
    if not inspect.iscoroutinefunction(testfunction):
        return None

    marker = pyfuncitem.get_closest_marker("asyncio")
    if marker is None and "anyio_backend" in pyfuncitem.funcargs:
        # Allow AnyIO's pytest plugin to manage coroutine execution when its
        # fixture is present so that backend-specific configuration (e.g., trio)
        # remains intact.
        return None

    signature = inspect.signature(testfunction)
    accepts_var_kwargs = any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in signature.parameters.values()
    )

    if accepts_var_kwargs:
        call_kwargs = pyfuncitem.funcargs
    else:
        call_kwargs = {
            name: value
            for name, value in pyfuncitem.funcargs.items()
            if name in signature.parameters
        }

    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        loop.run_until_complete(testfunction(**call_kwargs))
    finally:
        asyncio.set_event_loop(None)
        loop.close()

    return True
