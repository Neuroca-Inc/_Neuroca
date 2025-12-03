"""Metrics service facade used by the HTTP metrics API layer.

Purpose
-------
`MetricsService` provides an asynchronous, high-level interface for working
with metrics from FastAPI routes. It is intentionally implementation-agnostic:
metrics are stored in an in-process time-series ledger suitable for
development and early design-partner deployments.

The service is responsible for:

* Registering metric definitions (name, type, unit, retention).
* Recording individual metric samples with labels.
* Exposing time-series data and statistical summaries for API consumers.
* Providing a thin abstraction for per-tenant usage metering:
  - LLM call counts and token usage.
  - Memory CRUD operation counts.
  - Approximate memory storage footprint per tenant and tier.

External Dependencies
---------------------
This module only depends on:

* `neuroca.core.models.metrics` for API-facing DTOs.
* A generic `settings` object passed from `neuroca.config.settings.get_settings`.

It does **not** talk to external databases or monitoring backends. All data is
kept in memory, which is sufficient for:

* Local development.
* CI.
* Small design-partner deployments where external billing export will pull
  usage via the `/api/metrics/*` endpoints.

Timeout & Fallback Semantics
----------------------------
All methods operate in-memory and are expected to complete quickly. No explicit
timeout handling is required. When invalid parameters are provided, the service
raises `ValueError`. Missing metrics result in `KeyError` or empty responses
depending on the call:

* `get_metric_data` and `get_metric_summary` raise `KeyError` when the metric
  is unknown.
* Health/performance helpers return structurally correct, but minimal, data
  rather than failing.

These semantics are chosen to avoid making metrics a hard dependency for core
request paths while still providing meaningful information when available.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional

from neuroca.core.models.metrics import (
    MemoryMetrics,
    MetricDefinition,
    MetricSummary,
    MetricTimeseriesData,
    MetricType,
    PerformanceMetrics,
    SystemHealthMetrics,
)

# ---------------------------------------------------------------------------
# Internal data structures
# ---------------------------------------------------------------------------


@dataclass
class _MetricSample:
    """In-memory representation of a single metric sample.

    Attributes
    ----------
    timestamp:
        UTC timestamp when the sample was recorded.
    value:
        Numeric value of the sample (counter increment, gauge value, etc.).
    labels:
        Immutable dictionary of label key/value pairs attached to the sample.
    """

    timestamp: datetime
    value: float
    labels: Dict[str, str]


# Global, in-process time-series ledger for metrics.
# Keys are metric names; values are ordered lists of samples.
_SAMPLES: Dict[str, List[_MetricSample]] = {}

# Global registry of definitions keyed by metric name.
_DEFINITIONS: Dict[str, MetricDefinition] = {}

# Default retention window (in days) when a definition does not specify it.
_DEFAULT_RETENTION_DAYS = 30


def _now_utc() -> datetime:
    """Return the current UTC time without timezone info.

    The returned value is naive `datetime` in UTC for compatibility with
    existing models which expect naive timestamps.
    """
    return datetime.utcnow()


def _labels_match(sample_labels: Dict[str, str], required: Optional[Dict[str, str]]) -> bool:
    """Return True if ``sample_labels`` contains all key/value pairs in ``required``.

    Parameters
    ----------
    sample_labels:
        Labels attached to a recorded sample.
    required:
        Optional filter labels. When ``None`` or empty, all samples match.

    Returns
    -------
    bool
        ``True`` if the sample should be included for the given filter.
    """
    if not required:
        return True
    for key, expected in required.items():
        if sample_labels.get(key) != expected:
            return False
    return True


def _ensure_retention(name: str) -> None:
    """Trim samples for a metric according to its retention policy.

    Retention is applied using the metric definition's ``retention_days``
    field. If no definition exists, a default window is used. Samples older
    than ``now - retention_window`` are removed in-place.
    """
    if name not in _SAMPLES:
        return

    definition = _DEFINITIONS.get(name)
    retention_days = definition.retention_days if definition else _DEFAULT_RETENTION_DAYS
    cutoff = _now_utc() - timedelta(days=retention_days)

    samples = _SAMPLES[name]
    # Keep only samples newer than the cutoff.
    _SAMPLES[name] = [s for s in samples if s.timestamp >= cutoff]


def _parse_period(period: str) -> timedelta:
    """Parse a simple duration string into a ``timedelta``.

    Supported forms (case-insensitive)::

        "15m"  - 15 minutes
        "1h"   - 1 hour
        "24h"  - 24 hours
        "7d"   - 7 days

    Any unsupported or malformed value falls back to 24 hours.
    """
    if not period:
        return timedelta(hours=24)

    text = period.strip().lower()
    try:
        if text.endswith("m"):
            minutes = int(text[:-1])
            return timedelta(minutes=minutes)
        if text.endswith("h"):
            hours = int(text[:-1])
            return timedelta(hours=hours)
        if text.endswith("d"):
            days = int(text[:-1])
            return timedelta(days=days)
    except ValueError:
        # Fall through to default
        pass
    return timedelta(hours=24)


def _register_definition_if_missing(
    *,
    name: str,
    description: str,
    metric_type: MetricType,
    unit: str,
    labels: Optional[List[str]] = None,
    retention_days: int = _DEFAULT_RETENTION_DAYS,
) -> MetricDefinition:
    """Create a ``MetricDefinition`` if it does not already exist.

    This helper is idempotent and safe to call from multiple code paths that
    might want to ensure a metric is registered before recording samples.
    """
    existing = _DEFINITIONS.get(name)
    if existing is not None:
        return existing

    definition = MetricDefinition(
        name=name,
        description=description,
        type=metric_type,
        unit=unit,
        aggregation="last",
        retention_days=retention_days,
        labels=labels or [],
    )
    _DEFINITIONS[name] = definition
    return definition


# ---------------------------------------------------------------------------
# Public service
# ---------------------------------------------------------------------------


class MetricsService:
    """High-level metrics facade used by API routes.

    Instances of this class are lightweight; all state is stored in module
    globals so that multiple instances within a process share the same
    definitions and time-series ledger.

    Parameters
    ----------
    settings:
        Arbitrary settings object produced by :func:`get_settings`. Currently
        unused but accepted to keep the constructor stable if a persistent
        backend is introduced later.
    """

    def __init__(self, settings: Any) -> None:
        self._settings = settings
        self._ensure_usage_definitions()

    # ------------------------------------------------------------------ #
    # System / high-level metrics APIs
    # ------------------------------------------------------------------ #

    async def get_system_health(self) -> SystemHealthMetrics:
        """Return a minimal system health snapshot.

        The current implementation returns a structurally valid but
        conservative view that marks the system as "healthy" without
        pulling real-time data from lower-level health monitors. This is
        sufficient for dashboards and early design-partner environments.

        Returns
        -------
        SystemHealthMetrics
            Health metrics DTO suitable for the `/metrics/health` endpoint.
        """
        # We intentionally pass dictionaries so that the underlying models
        # can adapt even if their fields evolve.
        state_dict: Dict[str, Any] = {}
        components: List[Dict[str, Any]] = []
        return SystemHealthMetrics(state=state_dict, components=components)

    async def get_memory_metrics(self, tier: Optional[str] = None) -> MemoryMetrics:
        """Return a coarse memory metrics snapshot.

        Parameters
        ----------
        tier:
            Optional logical tier identifier. Currently used only as a label
            on the returned object.

        Returns
        -------
        MemoryMetrics
            DTO containing placeholder metrics for the requested tier.
        """
        utilization: Dict[str, Any] = {}
        effective_tier = tier or "all"
        return MemoryMetrics(
            tier=effective_tier,
            total_items=0,
            retrieval_latency_ms=0.0,
            hit_rate=0.0,
            utilization=utilization,
        )

    async def get_performance_metrics(
        self,
        *,
        component: Optional[str],
        period: str,
    ) -> PerformanceMetrics:
        """Return coarse performance metrics for a component or for the system.

        Parameters
        ----------
        component:
            Optional component identifier. Used only as metadata on the
            returned object.
        period:
            Human-readable period string (e.g. ``"1h"``). The current
            implementation does not yet adjust behaviour based on this value.

        Returns
        -------
        PerformanceMetrics
            DTO with placeholder indicators that can be safely extended later.
        """
        indicators: Dict[str, Any] = {}
        return PerformanceMetrics(
            component=component,
            indicators=indicators,
            timeframe=period,
        )

    # ------------------------------------------------------------------ #
    # Definition and sample management
    # ------------------------------------------------------------------ #

    async def register_metric_definition(
        self,
        *,
        name: str,
        description: str,
        metric_type: MetricType,
        unit: str,
        aggregation: str = "last",
        retention_days: int = _DEFAULT_RETENTION_DAYS,
        labels: Optional[List[str]] = None,
    ) -> MetricDefinition:
        """Register a metric definition or return the existing one.

        This call underpins the `/metrics/definitions` endpoint.

        Raises
        ------
        ValueError
            If the provided ``retention_days`` is not positive.
        """
        if retention_days <= 0:
            raise ValueError("retention_days must be positive")

        definition = _register_definition_if_missing(
            name=name,
            description=description,
            metric_type=metric_type,
            unit=unit,
            labels=labels,
            retention_days=retention_days,
        )
        # Preserve the caller's aggregation preference if different.
        definition.aggregation = aggregation or definition.aggregation
        return definition

    async def list_metric_definitions(self) -> List[MetricDefinition]:
        """Return all registered metric definitions."""
        return list(_DEFINITIONS.values())

    async def get_metric_definition(self, name: str) -> Optional[MetricDefinition]:
        """Return a specific metric definition, if it exists."""
        return _DEFINITIONS.get(name)

    async def delete_metric_definition(self, name: str) -> None:
        """Delete a metric definition and all of its samples."""
        _DEFINITIONS.pop(name, None)
        _SAMPLES.pop(name, None)

    async def record_metric(
        self,
        *,
        name: str,
        value: Any,
        timestamp: Optional[datetime] = None,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record a single metric sample.

        If the metric does not yet have a definition, a generic COUNTER
        definition in "count" units is created automatically. Callers that
        require stricter typing should register definitions explicitly first.

        Parameters
        ----------
        name:
            Metric name.
        value:
            Numeric value to record. Non-numeric values result in ``ValueError``.
        timestamp:
            Optional timestamp for the sample. When omitted, the current UTC
            time is used.
        labels:
            Optional label dictionary attached to the sample.
        """
        try:
            numeric_value = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Metric value for '{name}' must be numeric") from exc

        if name not in _DEFINITIONS:
            _register_definition_if_missing(
                name=name,
                description=f"Auto-registered metric '{name}'",
                metric_type=MetricType.COUNTER,
                unit="count",
            )

        labels_safe = dict(labels or {})
        sample = _MetricSample(
            timestamp=timestamp or _now_utc(),
            value=numeric_value,
            labels=labels_safe,
        )
        _SAMPLES.setdefault(name, []).append(sample)
        _ensure_retention(name)

    async def record_metrics_batch(
        self,
        *,
        metrics: Iterable[Dict[str, Any]],
    ) -> None:
        """Record a batch of metric samples.

        Parameters
        ----------
        metrics:
            Iterable of dictionaries with at least ``name`` and ``value``
            fields; optional ``timestamp`` and ``labels`` fields follow the
            same semantics as :meth:`record_metric`.
        """
        for item in metrics:
            await self.record_metric(
                name=str(item.get("name", "")),
                value=item.get("value", 0),
                timestamp=item.get("timestamp"),
                labels=item.get("labels"),
            )

    async def get_metric_data(
        self,
        *,
        name: str,
        start_time: datetime,
        end_time: datetime,
        interval: str,
        aggregation: Optional[str],
        limit: int,
        labels: Optional[Dict[str, str]] = None,
    ) -> MetricTimeseriesData:
        """Return time-series data for a metric.

        The current implementation returns raw samples filtered by time window
        and labels. The ``interval`` and ``aggregation`` parameters are
        accepted for API compatibility but do not yet change behaviour.

        Raises
        ------
        KeyError
            If the metric is unknown.
        """
        if name not in _DEFINITIONS:
            raise KeyError(f"Unknown metric: {name}")

        series = _SAMPLES.get(name, [])
        filtered: List[Dict[str, Any]] = []
        for sample in series:
            if sample.timestamp < start_time or sample.timestamp > end_time:
                continue
            if not _labels_match(sample.labels, labels):
                continue
            filtered.append(
                {
                    "timestamp": sample.timestamp,
                    "value": sample.value,
                }
            )

        if limit > 0 and len(filtered) > limit:
            filtered = filtered[-limit:]

        definition = _DEFINITIONS[name]
        return MetricTimeseriesData(
            name=name,
            unit=definition.unit,
            points=filtered,
        )

    async def get_metric_summary(self, *, name: str, period: str) -> MetricSummary:
        """Return a statistical summary for a metric over a period.

        The summary includes:

        * count
        * total (sum)
        * minimum
        * maximum
        * average
        * latest
        """
        if name not in _DEFINITIONS:
            raise KeyError(f"Unknown metric: {name}")

        window = _parse_period(period)
        end_time = _now_utc()
        start_time = end_time - window

        series = _SAMPLES.get(name, [])
        values: List[float] = [
            sample.value
            for sample in series
            if start_time <= sample.timestamp <= end_time
        ]

        if not values:
            values = [0.0]

        total = float(sum(values))
        count = len(values)
        minimum = float(min(values))
        maximum = float(max(values))
        average = total / count if count else 0.0
        latest = float(values[-1])

        definition = _DEFINITIONS[name]
        return MetricSummary(
            name=name,
            unit=definition.unit,
            count=count,
            total=total,
            minimum=minimum,
            maximum=maximum,
            average=average,
            latest=latest,
        )

    # ------------------------------------------------------------------ #
    # Higher-level dashboards and alerts
    # ------------------------------------------------------------------ #

    async def get_metrics_dashboard(
        self,
        *,
        dashboard_id: Optional[str],
        metrics: Optional[List[str]],
        period: str,
    ) -> Dict[str, Any]:
        """Return a simple dashboard payload.

        This implementation groups summaries for either the requested metrics
        or all known metrics when ``metrics`` is ``None``. The ``dashboard_id``
        parameter is reserved for future persisted layouts.
        """
        if metrics is None:
            metric_names = list(_DEFINITIONS.keys())
        else:
            metric_names = [m for m in metrics if m in _DEFINITIONS]

        summaries: Dict[str, Any] = {}
        for name in metric_names:
            try:
                summary = await self.get_metric_summary(name=name, period=period)
            except KeyError:
                continue
            summaries[name] = {
                "unit": summary.unit,
                "count": summary.count,
                "total": summary.total,
                "average": summary.average,
            }

        return {
            "dashboard_id": dashboard_id,
            "period": period,
            "summaries": summaries,
        }

    async def export_metrics(
        self,
        *,
        metrics: List[str],
        start_time: datetime,
        end_time: datetime,
        format: str,
    ) -> Any:
        """Export metrics data in JSON-serialisable form.

        Parameters
        ----------
        metrics:
            List of metric names to export.
        start_time, end_time:
            Time window for export.
        format:
            Export format. Currently ``"json"`` and ``"csv"`` are recognised.
            For ``"json"`` the method returns a dictionary; for ``"csv"`` it
            returns a CSV-formatted string.
        """
        selected = [m for m in metrics if m in _DEFINITIONS]
        export_payload: Dict[str, Any] = {}

        for name in selected:
            data = await self.get_metric_data(
                name=name,
                start_time=start_time,
                end_time=end_time,
                interval="1m",
                aggregation=None,
                limit=10_000,
                labels=None,
            )
            export_payload[name] = [
                {"timestamp": p["timestamp"].isoformat(), "value": p["value"]}
                for p in data.points
            ]

        if format.lower() == "csv":
            # Simple CSV: metric_name,timestamp_iso,value
            lines: List[str] = ["metric,timestamp,value"]
            for metric_name, samples in export_payload.items():
                for sample in samples:
                    lines.append(
                        f"{metric_name},{sample['timestamp']},{sample['value']}"
                    )
            return "\n".join(lines)

        # Default to JSON-style dictionary.
        return export_payload

    async def get_metric_alerts(
        self,
        *,
        status: Optional[str],
        severity: Optional[str],
    ) -> List[Dict[str, Any]]:
        """Return a minimal list of metric alerts.

        The current implementation does not perform real thresholding. It
        returns an empty list, preserving the response shape expected by the
        `/metrics/alerts` endpoint.
        """
        _ = status
        _ = severity
        return []

    async def get_metrics_overview(self) -> Dict[str, Any]:
        """Return a high-level overview of metrics currently stored.

        Returns
        -------
        dict
            Dictionary containing a list of definitions and basic usage
            statistics. The `/metrics` route attaches additional metadata.
        """
        total_samples = sum(len(series) for series in _SAMPLES.values())
        return {
            "definitions": [d.name for d in _DEFINITIONS.values()],
            "counts": {
                "metrics": len(_DEFINITIONS),
                "samples": total_samples,
            },
        }

    # ------------------------------------------------------------------ #
    # Per-tenant usage metering helpers (Task C1)
    # ------------------------------------------------------------------ #

    def _ensure_usage_definitions(self) -> None:
        """Ensure core per-tenant usage metrics are registered.

        This method is idempotent and safe to call from multiple instances.
        """
        _register_definition_if_missing(
            name="usage.llm.calls",
            description="Total LLM calls per tenant and user",
            metric_type=MetricType.COUNTER,
            unit="count",
            labels=["tenant_id", "user_id", "provider", "model"],
        )
        _register_definition_if_missing(
            name="usage.llm.tokens.prompt",
            description="Total prompt tokens per tenant and user",
            metric_type=MetricType.COUNTER,
            unit="tokens",
            labels=["tenant_id", "user_id", "provider", "model"],
        )
        _register_definition_if_missing(
            name="usage.llm.tokens.completion",
            description="Total completion tokens per tenant and user",
            metric_type=MetricType.COUNTER,
            unit="tokens",
            labels=["tenant_id", "user_id", "provider", "model"],
        )
        _register_definition_if_missing(
            name="usage.llm.tokens.total",
            description="Total tokens per tenant and user",
            metric_type=MetricType.COUNTER,
            unit="tokens",
            labels=["tenant_id", "user_id", "provider", "model"],
        )
        _register_definition_if_missing(
            name="usage.memory.operations.create",
            description="Memory create operations per tenant and user",
            metric_type=MetricType.COUNTER,
            unit="count",
            labels=["tenant_id", "user_id", "tier"],
        )
        _register_definition_if_missing(
            name="usage.memory.operations.read",
            description="Memory read operations per tenant and user",
            metric_type=MetricType.COUNTER,
            unit="count",
            labels=["tenant_id", "user_id", "tier"],
        )
        _register_definition_if_missing(
            name="usage.memory.operations.update",
            description="Memory update operations per tenant and user",
            metric_type=MetricType.COUNTER,
            unit="count",
            labels=["tenant_id", "user_id", "tier"],
        )
        _register_definition_if_missing(
            name="usage.memory.operations.delete",
            description="Memory delete operations per tenant and user",
            metric_type=MetricType.COUNTER,
            unit="count",
            labels=["tenant_id", "user_id", "tier"],
        )
        _register_definition_if_missing(
            name="usage.memory.storage.bytes",
            description="Approximate memory storage footprint per tenant and tier",
            metric_type=MetricType.GAUGE,
            unit="bytes",
            labels=["tenant_id", "tier"],
        )

    async def record_llm_usage(
        self,
        *,
        tenant_id: Optional[str],
        user_id: Optional[str],
        provider: str,
        model: str,
        prompt_tokens: Optional[int],
        completion_tokens: Optional[int],
        total_tokens: Optional[int],
    ) -> None:
        """Record per-tenant LLM usage metrics for a single call.

        The method is tolerant of ``None`` values for any token counts and
        simply skips recording those metrics when they are unavailable.

        Parameters
        ----------
        tenant_id, user_id:
            Logical tenant and user identifiers. When ``None`` they are
            recorded as ``"unknown"`` so that downstream aggregation remains
            well-formed.
        provider, model:
            LLM provider and model identifiers (e.g. ``"ollama"``,
            ``"gemma3:4b"``).
        prompt_tokens, completion_tokens, total_tokens:
            Token counts reported by the underlying LLM provider.
        """
        labels = {
            "tenant_id": tenant_id or "unknown",
            "user_id": user_id or "unknown",
            "provider": provider,
            "model": model,
        }

        await self.record_metric(name="usage.llm.calls", value=1, labels=labels)

        if prompt_tokens is not None:
            await self.record_metric(
                name="usage.llm.tokens.prompt",
                value=prompt_tokens,
                labels=labels,
            )
        if completion_tokens is not None:
            await self.record_metric(
                name="usage.llm.tokens.completion",
                value=completion_tokens,
                labels=labels,
            )
        if total_tokens is not None:
            await self.record_metric(
                name="usage.llm.tokens.total",
                value=total_tokens,
                labels=labels,
            )

    async def record_memory_operation(
        self,
        *,
        tenant_id: Optional[str],
        user_id: Optional[str],
        operation: str,
        tier: Optional[str],
        size_bytes: Optional[int] = None,
    ) -> None:
        """Record a per-tenant memory operation metric.

        Parameters
        ----------
        tenant_id, user_id:
            Logical tenant and user identifiers; normalised to non-empty
            strings.
        operation:
            Operation kind: one of ``"create"``, ``"read"``, ``"update"``,
            or ``"delete"``. Unknown values are ignored.
        tier:
            Logical memory tier (e.g. ``"stm"``, ``"mtm"``, ``"ltm"``). When
            ``None`` a generic ``"unknown"`` label is used.
        size_bytes:
            Optional approximate size delta for storage footprint tracking.
            When provided for a create or delete operation, it is recorded
            against the ``usage.memory.storage.bytes`` gauge for the given
            tenant and tier.
        """
        op = operation.strip().lower()
        if op not in {"create", "read", "update", "delete"}:
            return

        labels = {
            "tenant_id": tenant_id or "unknown",
            "user_id": user_id or "unknown",
            "tier": tier or "unknown",
        }

        metric_name = f"usage.memory.operations.{op}"
        if metric_name in _DEFINITIONS:
            await self.record_metric(name=metric_name, value=1, labels=labels)

        # Storage footprint tracking (best-effort, approximate).
        if size_bytes is not None and op in {"create", "delete"}:
            storage_labels = {
                "tenant_id": labels["tenant_id"],
                "tier": labels["tier"],
            }
            delta = float(size_bytes)
            if op == "delete":
                delta = -delta

            # Retrieve the latest value so we can adjust the gauge.
            series = _SAMPLES.get("usage.memory.storage.bytes", [])
            current_value = 0.0
            for sample in reversed(series):
                if _labels_match(sample.labels, storage_labels):
                    current_value = sample.value
                    break

            new_value = max(0.0, current_value + delta)
            await self.record_metric(
                name="usage.memory.storage.bytes",
                value=new_value,
                labels=storage_labels,
            )


__all__ = ["MetricsService"]