"""Decorators that provide tracing spans for synchronous and async callables."""

from __future__ import annotations

import asyncio
import functools
from typing import Any, Callable, Optional, TypeVar

from opentelemetry import trace

from .context import current_trace_id

F = TypeVar("F", bound=Callable[..., Any])

__all__ = ["with_traced_function"]


def with_traced_function(name: Optional[str] = None) -> Callable[[F], F]:
    """Wrap a callable so execution is recorded inside an OpenTelemetry span.

    Args:
        name: Optional name used for the emitted span. When omitted the
            decorated callable's ``__name__`` attribute is used.

    Returns:
        Callable[[F], F]: A decorator that records the wrapped function's
            execution inside a span and re-raises any exceptions encountered.
    """

    def decorator(func: F) -> F:
        span_name = name or func.__name__
        tracer = trace.get_tracer(__name__)

        if asyncio.iscoroutinefunction(func):  # type: ignore[arg-type]

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                with tracer.start_as_current_span(span_name) as span:
                    _record_arguments(span, args, kwargs)
                    try:
                        return await func(*args, **kwargs)
                    except Exception as exc:  # pragma: no cover - defensive path
                        span.record_exception(exc)
                        span.set_status(
                            trace.Status(trace.StatusCode.ERROR, str(exc))
                        )
                        raise

            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            with tracer.start_as_current_span(span_name) as span:
                _record_arguments(span, args, kwargs)
                try:
                    return func(*args, **kwargs)
                except Exception as exc:  # pragma: no cover - defensive path
                    span.record_exception(exc)
                    span.set_status(trace.Status(trace.StatusCode.ERROR, str(exc)))
                    raise

        return sync_wrapper  # type: ignore[return-value]

    return decorator


def _record_arguments(span: trace.Span, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
    """Store safe function arguments on the provided span for diagnostics.

    Args:
        span: Span that should receive the argument metadata.
        args: Positional arguments supplied to the wrapped callable.
        kwargs: Keyword arguments supplied to the wrapped callable.

    Returns:
        None: The function mutates ``span`` directly.
    """

    safe_args: dict[str, str]
    if args and hasattr(args[0], "__class__"):
        safe_args = {f"arg_{index}": str(arg) for index, arg in enumerate(args[1:])}
    else:
        safe_args = {f"arg_{index}": str(arg) for index, arg in enumerate(args)}

    safe_kwargs = {
        key: str(value)
        for key, value in kwargs.items()
        if not any(
            sensitive in key.lower()
            for sensitive in ["password", "token", "secret", "key", "auth"]
        )
    }

    for key, value in safe_args.items():
        span.set_attribute(key, value)

    for key, value in safe_kwargs.items():
        span.set_attribute(key, value)

    if hasattr(span, "get_span_context"):
        span_context = span.get_span_context()
        if span_context.trace_id:
            current_trace_id.set(format(span_context.trace_id, "032x"))
