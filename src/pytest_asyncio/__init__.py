"""Lightweight pytest-asyncio compatibility layer.

This module provides the subset of the public ``pytest_asyncio`` surface
required by the Neuroca test-suite without depending on the upstream
package.  It offers a ``fixture`` decorator capable of executing
``async`` fixtures as well as async generator fixtures and exposes the
plugin that drives ``pytest.mark.asyncio`` tests.
"""

from __future__ import annotations

import asyncio
import inspect
from functools import wraps
from typing import Any, Callable, Generator, TypeVar

import pytest

__all__ = ["fixture", "__version__"]
__version__ = "0.0.0-local"
pytest_plugins = ["pytest_asyncio.plugin"]

_FixtureFunc = TypeVar("_FixtureFunc", bound=Callable[..., Any])


def fixture(*args: Any, **kwargs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorate an async fixture so it executes within an event loop.

    The decorator mirrors ``pytest_asyncio.fixture`` for the limited use
    cases present in the repository: async regular fixtures and async
    generator fixtures.  Each invocation is executed inside a dedicated
    event loop to avoid cross-test interference while still running the
    async cleanup section (``yield`` body) before the loop is disposed.
    """

    def _decorate(func: _FixtureFunc) -> _FixtureFunc:
        if inspect.isasyncgenfunction(func):
            @pytest.fixture(*args, **kwargs)
            @wraps(func)
            def _async_gen_wrapper(*f_args: Any, **f_kwargs: Any) -> Generator[Any, None, None]:
                loop = asyncio.new_event_loop()
                try:
                    asyncio.set_event_loop(loop)
                    agen = func(*f_args, **f_kwargs)
                    try:
                        value = loop.run_until_complete(agen.__anext__())
                    except StopAsyncIteration as exc:  # pragma: no cover - defensive
                        raise RuntimeError("Async fixture generated no values") from exc
                    try:
                        yield value
                    finally:
                        loop.run_until_complete(agen.aclose())
                finally:
                    asyncio.set_event_loop(None)
                    loop.close()

            return _async_gen_wrapper  # type: ignore[return-value]

        if inspect.iscoroutinefunction(func):
            @pytest.fixture(*args, **kwargs)
            @wraps(func)
            def _async_wrapper(*f_args: Any, **f_kwargs: Any) -> Any:
                loop = asyncio.new_event_loop()
                try:
                    asyncio.set_event_loop(loop)
                    return loop.run_until_complete(func(*f_args, **f_kwargs))
                finally:
                    asyncio.set_event_loop(None)
                    loop.close()

            return _async_wrapper  # type: ignore[return-value]

        # Fallback to the standard pytest fixture decorator for sync callables.
        return pytest.fixture(*args, **kwargs)(func)  # type: ignore[return-value]

    if args and callable(args[0]) and len(args) == 1 and not kwargs:
        return _decorate(args[0])  # type: ignore[return-value]

    return _decorate
