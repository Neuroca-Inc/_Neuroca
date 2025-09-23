"""Metrics publication helpers for the memory manager."""

from __future__ import annotations

import logging
import time
from typing import Any, Mapping, MutableMapping, Sequence

from neuroca.monitoring.metrics.exporters import (
    ConfigurationError,
    MetricExporter,
    MetricType,
    PrometheusExporter,
)


class MemoryMetricsPublisher:
    """Publish memory lifecycle metrics via the Prometheus exporter plumbing."""

    DEFAULT_TIERS: Sequence[str] = ("stm", "mtm", "ltm")

    def __init__(
        self,
        config: Mapping[str, Any] | None = None,
        *,
        log: logging.Logger | None = None,
        exporter: MetricExporter | None = None,
    ) -> None:
        self._log = log or logging.getLogger(__name__)
        self._config = dict(config or {})
        tiers = self._config.get("tiers")
        if isinstance(tiers, Sequence) and tiers:
            self._tiers: tuple[str, ...] = tuple(str(tier) for tier in tiers)
        else:
            self._tiers = tuple(self.DEFAULT_TIERS)

        self._enabled = bool(self._config.get("enabled", True))
        self._exporter: MetricExporter | None = exporter

        if not self._enabled:
            self._exporter = None
            return

        if self._exporter is None:
            name = str(self._config.get("name", "memory_manager"))
            endpoint = str(self._config.get("endpoint", "/metrics"))
            host = str(self._config.get("host", "0.0.0.0"))
            port = self._coerce_int(self._config.get("port", 9464), default=9464)
            batch_size = self._coerce_int(self._config.get("batch_size", 100), default=100)
            flush_interval = self._coerce_int(self._config.get("flush_interval", 15), default=15)

            try:
                self._exporter = PrometheusExporter(
                    name=name,
                    endpoint=endpoint,
                    host=host,
                    port=port,
                    batch_size=batch_size,
                    flush_interval=flush_interval,
                )
            except ConfigurationError as exc:  # pragma: no cover - depends on runtime deps
                self._log.warning("Disabling memory metrics exporter: %s", exc)
                self._enabled = False
                self._exporter = None

        self._known_capacity: dict[str, float] = {}

    @property
    def enabled(self) -> bool:
        """Return ``True`` when metrics emission is active."""

        return self._enabled and self._exporter is not None

    # ------------------------------------------------------------------
    # Consolidation metrics
    # ------------------------------------------------------------------

    def record_consolidation(
        self,
        *,
        source: str,
        target: str,
        duration_seconds: float | None,
        succeeded: bool,
    ) -> None:
        """Record a consolidation attempt outcome."""

        if not self.enabled:
            return

        base_labels = {"source": source, "target": target}
        status_labels = dict(base_labels)
        status_labels["status"] = "success" if succeeded else "failure"

        if succeeded:
            self._emit(
                "memory_consolidation_promotions_total",
                1.0,
                labels=base_labels,
                metric_type=MetricType.COUNTER,
            )
        else:
            self._emit(
                "memory_consolidation_failures_total",
                1.0,
                labels=base_labels,
                metric_type=MetricType.COUNTER,
            )

        if duration_seconds is not None:
            self._emit(
                "memory_consolidation_latency_ms",
                max(0.0, float(duration_seconds) * 1000.0),
                labels=status_labels,
                metric_type=MetricType.HISTOGRAM,
            )

    # ------------------------------------------------------------------
    # Maintenance telemetry sink
    # ------------------------------------------------------------------

    def handle_cycle_report(self, payload: Mapping[str, Any]) -> None:
        """Consume maintenance reports emitted by the orchestrator."""

        if not self.enabled:
            return

        consolidation = self._coerce_mapping(payload.get("consolidation"))
        duration = self._coerce_float(payload.get("duration_seconds"))
        telemetry = self._coerce_mapping(payload.get("telemetry"))

        self._publish_promotion_rates(consolidation, duration)
        self._publish_decay_counts(self._coerce_mapping(payload.get("decay")))
        self._publish_orphan_gauges(self._coerce_mapping(payload.get("cleanup")))
        self._publish_backlog_age(telemetry)

        drift_summary = self._coerce_mapping(payload.get("drift"))
        if drift_summary:
            self.publish_embedding_drift(
                quality_score=self._coerce_float(drift_summary.get("quality_score")),
                quality_delta=self._coerce_float(drift_summary.get("quality_delta")),
                integrity_report=self._coerce_mapping(drift_summary.get("integrity")),
                alerts=self._coerce_sequence(drift_summary.get("alerts")),
            )

    # ------------------------------------------------------------------
    # Capacity utilisation updates
    # ------------------------------------------------------------------

    def update_capacity_snapshot(self, snapshot: Mapping[str, Any]) -> None:
        """Update utilisation gauges using the latest capacity adapter snapshot."""

        if not self.enabled:
            return

        tiers = set(self._tiers)
        for tier in snapshot:
            tiers.add(str(tier))

        for tier in sorted(tiers):
            tier_snapshot = self._coerce_mapping(snapshot.get(tier, {}))
            ratio = self._coerce_float(tier_snapshot.get("ratio"), default=0.0)
            ratio = max(0.0, min(1.0, ratio))
            self._known_capacity[tier] = ratio
            self._emit(
                "memory_tier_utilization_percent",
                ratio * 100.0,
                labels={"tier": tier},
                metric_type=MetricType.GAUGE,
            )

        # Ensure tiers with no data are flushed to zero so old values do not linger
        for tier in self._tiers:
            if tier not in snapshot:
                prior = self._known_capacity.get(tier, 0.0)
                if prior != 0.0:
                    self._emit(
                        "memory_tier_utilization_percent",
                        0.0,
                        labels={"tier": tier},
                        metric_type=MetricType.GAUGE,
                    )
                    self._known_capacity[tier] = 0.0

    # ------------------------------------------------------------------
    # Drift detection metrics
    # ------------------------------------------------------------------

    def publish_embedding_drift(
        self,
        *,
        quality_score: float | None,
        quality_delta: float | None,
        integrity_report: Mapping[str, Any],
        alerts: Sequence[Any],
    ) -> None:
        """Publish gauges describing embedding drift state."""

        if not self.enabled:
            return

        if quality_score is not None:
            self._emit(
                "memory_embedding_drift_score",
                quality_score,
                metric_type=MetricType.GAUGE,
            )

        if quality_delta is not None:
            self._emit(
                "memory_embedding_drift_delta",
                max(0.0, quality_delta),
                metric_type=MetricType.GAUGE,
            )

        drifted_ids = integrity_report.get("drifted_ids")
        if isinstance(drifted_ids, Sequence) and not isinstance(drifted_ids, (str, bytes)):
            self._emit(
                "memory_vector_index_drifted_entries",
                float(len(drifted_ids)),
                metric_type=MetricType.GAUGE,
            )

        max_drift = self._coerce_float(integrity_report.get("max_drift"), default=0.0)
        self._emit(
            "memory_vector_index_max_drift",
            max_drift,
            metric_type=MetricType.GAUGE,
        )

        severity = "none"
        alert_count = 0
        if isinstance(alerts, Sequence) and not isinstance(alerts, (str, bytes)):
            alert_count = len(alerts)
            if alerts:
                first = alerts[0]
                if isinstance(first, Mapping):
                    severity = str(first.get("severity", severity))

        self._emit(
            "memory_embedding_drift_alerts",
            float(alert_count),
            labels={"severity": severity},
            metric_type=MetricType.GAUGE,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _publish_promotion_rates(
        self, consolidation: Mapping[str, Any], duration_seconds: float
    ) -> None:
        duration = max(0.0, duration_seconds)
        paths = {
            "stm_to_mtm": self._coerce_int(consolidation.get("stm_to_mtm")),
            "mtm_to_ltm": self._coerce_int(consolidation.get("mtm_to_ltm")),
        }
        total = self._coerce_int(consolidation.get("total"))
        if not total:
            total = sum(paths.values())

        for path, count in {**paths, "total": total}.items():
            rate = (count / duration) if duration > 0 else 0.0
            self._emit(
                "memory_promotions_per_second",
                rate,
                labels={"path": path},
                metric_type=MetricType.GAUGE,
            )

    def _publish_decay_counts(self, decay: Mapping[str, Any]) -> None:
        total = 0
        for tier in self._tiers:
            stats = self._coerce_mapping(decay.get(tier))
            count = self._coerce_int(stats.get("decayed")) + self._coerce_int(
                stats.get("removed")
            )
            total += count
            self._emit(
                "memory_decay_events_total",
                float(count),
                labels={"tier": tier},
                metric_type=MetricType.COUNTER,
            )

        self._emit(
            "memory_decay_events_total",
            float(total),
            labels={"tier": "all"},
            metric_type=MetricType.COUNTER,
        )

    def _publish_orphan_gauges(self, cleanup: Mapping[str, Any]) -> None:
        total = 0
        for tier in self._tiers:
            removed = self._coerce_int(
                self._coerce_mapping(cleanup.get(tier)).get("removed")
            )
            total += removed
            self._emit(
                "memory_orphaned_items",
                float(removed),
                labels={"tier": tier},
                metric_type=MetricType.GAUGE,
            )

        self._emit(
            "memory_orphaned_items",
            float(total),
            labels={"tier": "all"},
            metric_type=MetricType.GAUGE,
        )

    def _publish_backlog_age(self, telemetry: Mapping[str, Any]) -> None:
        if not telemetry:
            self._emit(
                "memory_maintenance_backlog_age_seconds",
                0.0,
                labels={"scope": "maintenance"},
                metric_type=MetricType.GAUGE,
            )
            return

        last_completed = self._coerce_float(telemetry.get("last_completed_at"), default=0.0)
        if last_completed <= 0.0:
            last_completed = self._coerce_float(telemetry.get("last_started_at"), default=0.0)

        backlog_age = 0.0
        if last_completed > 0.0:
            backlog_age = max(0.0, time.time() - last_completed)

        self._emit(
            "memory_maintenance_backlog_age_seconds",
            backlog_age,
            labels={"scope": "maintenance"},
            metric_type=MetricType.GAUGE,
        )

    def _emit(
        self,
        name: str,
        value: float,
        *,
        labels: MutableMapping[str, str] | None = None,
        metric_type: MetricType = MetricType.GAUGE,
    ) -> None:
        if not self.enabled or self._exporter is None:
            return

        try:
            self._exporter.export_metric(
                name,
                float(value),
                labels=dict(labels or {}),
                metric_type=metric_type,
            )
        except Exception:  # noqa: BLE001 - metrics must never break control flow
            self._log.debug("Failed to export metric %s", name, exc_info=True)

    @staticmethod
    def _coerce_int(candidate: Any, *, default: int = 0) -> int:
        try:
            return int(candidate)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _coerce_float(candidate: Any, *, default: float = 0.0) -> float:
        try:
            return float(candidate)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _coerce_mapping(candidate: Any) -> Mapping[str, Any]:
        if isinstance(candidate, Mapping):
            return candidate
        return {}

    @staticmethod
    def _coerce_sequence(candidate: Any) -> Sequence[Any]:
        if isinstance(candidate, Sequence) and not isinstance(candidate, (str, bytes)):
            return candidate
        return ()

