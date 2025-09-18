from __future__ import annotations

import enum
import json
import uuid
from collections import OrderedDict
from dataclasses import asdict, is_dataclass
from datetime import datetime
from time import monotonic
from typing import Any, Mapping

from .base import BaseEvent


class EventIdempotencyFilter:
    """Track recently emitted events to avoid publishing duplicates."""

    def __init__(
        self,
        *,
        ttl_seconds: float = 600.0,
        max_entries: int = 2048,
    ) -> None:
        self._ttl = max(0.0, float(ttl_seconds))
        self._max_entries = max(1, int(max_entries))
        self._seen: OrderedDict[str, float] = OrderedDict()

    def should_emit(self, fingerprint: str) -> bool:
        """Return ``True`` when ``fingerprint`` has not been seen recently."""

        now = monotonic()
        self._prune(now)

        if fingerprint in self._seen:
            self._seen[fingerprint] = now
            return False

        self._seen[fingerprint] = now
        if len(self._seen) > self._max_entries:
            self._seen.popitem(last=False)
        return True

    def _prune(self, now: float) -> None:
        if self._ttl <= 0:
            # TTL disabled – only enforce bounded cache size.
            while len(self._seen) > self._max_entries:
                self._seen.popitem(last=False)
            return

        cutoff = now - self._ttl
        while self._seen:
            oldest_key, timestamp = next(iter(self._seen.items()))
            if timestamp >= cutoff:
                break
            self._seen.popitem(last=False)


def event_fingerprint(event: BaseEvent | Mapping[str, Any]) -> str:
    """Return a stable fingerprint string for ``event``."""

    payload = _event_payload(event)
    normalized = _normalize(payload)
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"))


def deterministic_event_id(fingerprint: str) -> str:
    """Return a deterministic identifier for ``fingerprint``."""

    return str(uuid.uuid5(uuid.NAMESPACE_URL, fingerprint))


def _event_payload(event: BaseEvent | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(event, Mapping):
        payload = dict(event)
    elif is_dataclass(event):
        payload = asdict(event)
    else:
        payload = dict(vars(event))

    payload.pop("id", None)
    payload.pop("timestamp", None)
    return payload


def _normalize(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _normalize(sub_value) for key, sub_value in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    if isinstance(value, set):
        return sorted(_normalize(item) for item in value)
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    return value


__all__ = [
    "EventIdempotencyFilter",
    "deterministic_event_id",
    "event_fingerprint",
]
