"""Embedding drift monitoring helpers for the memory manager."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Mapping, Optional, Sequence

from neuroca.memory.manager.events import MaintenanceEventPublisher
from neuroca.memory.manager.metrics import MemoryMetricsPublisher


VectorIntegrityReport = Mapping[str, Any]
QualityReport = Mapping[str, Any]


@dataclass(slots=True)
class _QualitySnapshot:
    """Capture quality drift metrics from the latest evaluation."""

    report: dict[str, Any]
    score: float | None
    delta: float | None


class EmbeddingDriftMonitor:
    """Periodically evaluate embedding drift and emit notifications."""

    DEFAULT_INTERVAL_SECONDS = 900.0
    DEFAULT_QUALITY_ALERT_THRESHOLD = 0.65
    DEFAULT_QUALITY_CRITICAL_THRESHOLD = 0.85
    DEFAULT_QUALITY_DELTA_THRESHOLD = 0.15
    DEFAULT_INTEGRITY_CHECK_THRESHOLD = 0.1
    DEFAULT_INTEGRITY_ALERT_THRESHOLD = 0.2
    DEFAULT_INTEGRITY_CRITICAL_THRESHOLD = 0.4
    DEFAULT_SAMPLE_SIZE = 200

    def __init__(
        self,
        *,
        enabled: bool = True,
        interval_seconds: float = DEFAULT_INTERVAL_SECONDS,
        quality_alert_threshold: float = DEFAULT_QUALITY_ALERT_THRESHOLD,
        quality_critical_threshold: float = DEFAULT_QUALITY_CRITICAL_THRESHOLD,
        quality_delta_threshold: float = DEFAULT_QUALITY_DELTA_THRESHOLD,
        integrity_check_threshold: float = DEFAULT_INTEGRITY_CHECK_THRESHOLD,
        integrity_alert_threshold: float = DEFAULT_INTEGRITY_ALERT_THRESHOLD,
        integrity_critical_threshold: float = DEFAULT_INTEGRITY_CRITICAL_THRESHOLD,
        integrity_sample_size: int = DEFAULT_SAMPLE_SIZE,
        log: logging.Logger | None = None,
    ) -> None:
        self._enabled = bool(enabled)
        self._interval = max(0.0, float(interval_seconds))
        self._quality_alert_threshold = max(0.0, float(quality_alert_threshold))
        self._quality_critical_threshold = max(0.0, float(quality_critical_threshold))
        self._quality_delta_threshold = max(0.0, float(quality_delta_threshold))
        self._integrity_check_threshold = max(0.0, float(integrity_check_threshold))
        self._integrity_alert_threshold = max(0.0, float(integrity_alert_threshold))
        self._integrity_critical_threshold = max(0.0, float(integrity_critical_threshold))
        self._integrity_sample_size = max(0, int(integrity_sample_size))
        self._log = log or logging.getLogger(__name__).getChild("drift")

        self._vector_backend: Any | None = None
        self._metrics: MemoryMetricsPublisher | None = None
        self._event_publisher: MaintenanceEventPublisher | None = None
        self._quality_provider: Callable[[], Awaitable[QualityReport]] | None = None

        self._lock = asyncio.Lock()
        self._last_check: float | None = None
        self._last_quality_score: float | None = None
        self._last_report: dict[str, Any] | None = None
        self._last_alert_signature: tuple[Any, ...] | None = None
        self._quality_alert_active = False

    @classmethod
    def from_config(
        cls,
        config: Mapping[str, Any],
        *,
        log: logging.Logger | None = None,
    ) -> "EmbeddingDriftMonitor":
        """Instantiate a drift monitor using configuration inputs."""

        cfg = dict(config or {})

        return cls(
            enabled=bool(cfg.get("enabled", True)),
            interval_seconds=cls._coerce_positive_float(
                cfg.get("interval_seconds"),
                fallback=cls.DEFAULT_INTERVAL_SECONDS,
            ),
            quality_alert_threshold=cls._coerce_positive_float(
                cfg.get("quality_alert_threshold"),
                fallback=cls.DEFAULT_QUALITY_ALERT_THRESHOLD,
            ),
            quality_critical_threshold=cls._coerce_positive_float(
                cfg.get("quality_critical_threshold"),
                fallback=cls.DEFAULT_QUALITY_CRITICAL_THRESHOLD,
            ),
            quality_delta_threshold=cls._coerce_positive_float(
                cfg.get("quality_delta_threshold"),
                fallback=cls.DEFAULT_QUALITY_DELTA_THRESHOLD,
            ),
            integrity_check_threshold=cls._coerce_positive_float(
                cfg.get("integrity_check_threshold"),
                fallback=cls.DEFAULT_INTEGRITY_CHECK_THRESHOLD,
            ),
            integrity_alert_threshold=cls._coerce_positive_float(
                cfg.get("integrity_alert_threshold"),
                fallback=cls.DEFAULT_INTEGRITY_ALERT_THRESHOLD,
            ),
            integrity_critical_threshold=cls._coerce_positive_float(
                cfg.get("integrity_critical_threshold"),
                fallback=cls.DEFAULT_INTEGRITY_CRITICAL_THRESHOLD,
            ),
            integrity_sample_size=cls._coerce_positive_int(
                cfg.get("integrity_sample_size"),
                fallback=cls.DEFAULT_SAMPLE_SIZE,
            ),
            log=log,
        )

    @property
    def enabled(self) -> bool:
        """Return ``True`` when drift monitoring is active."""

        return self._enabled

    @property
    def interval_seconds(self) -> float:
        """Expose the configured monitoring interval."""

        return self._interval

    @property
    def last_report(self) -> dict[str, Any] | None:
        """Return the most recent drift evaluation report."""

        if self._last_report is None:
            return None
        return dict(self._last_report)

    def configure(
        self,
        *,
        vector_backend: Any | None,
        metrics: MemoryMetricsPublisher | None,
        event_publisher: MaintenanceEventPublisher | None,
        quality_provider: Callable[[], Awaitable[QualityReport]] | None = None,
    ) -> None:
        """Attach runtime dependencies used during drift evaluation."""

        self._vector_backend = vector_backend
        self._metrics = metrics
        self._event_publisher = event_publisher
        self._quality_provider = quality_provider

    async def run_checks(
        self,
        *,
        quality_report: Mapping[str, Any] | None = None,
        force: bool = False,
        sample_size: int | None = None,
    ) -> dict[str, Any] | None:
        """Evaluate drift metrics and emit notifications when thresholds trip."""

        if not self.enabled:
            return None

        backend = self._vector_backend
        if backend is None or not hasattr(backend, "check_index_integrity"):
            self._log.debug("Drift monitor skipped: vector backend unavailable")
            return None

        now = time.time()
        if not force and not self._should_run(now):
            return None

        async with self._lock:
            if not force and not self._should_run(now):
                return None

            quality_snapshot = await self._collect_quality_snapshot(quality_report)

            integrity = await backend.check_index_integrity(  # type: ignore[func-returns-value]
                drift_threshold=self._integrity_check_threshold,
                sample_size=sample_size if sample_size is not None else self._integrity_sample_size,
            )
            integrity_report = self._coerce_integrity_report(integrity)

            alerts = self._build_alerts(quality_snapshot, integrity_report)
            timestamp = datetime.fromtimestamp(now, tz=timezone.utc).isoformat()

            summary = {
                "checked_at": timestamp,
                "quality": quality_snapshot.report,
                "quality_score": quality_snapshot.score,
                "quality_delta": quality_snapshot.delta,
                "integrity": integrity_report,
                "alerts": alerts,
            }

            self._last_report = summary
            self._last_check = now
            if quality_snapshot.score is not None:
                self._last_quality_score = quality_snapshot.score

            self._publish_metrics(summary)
            await self._emit_alerts(summary)

            return summary

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _collect_quality_snapshot(
        self, provided: Mapping[str, Any] | None
    ) -> _QualitySnapshot:
        report: dict[str, Any]
        if provided is None and self._quality_provider is not None:
            try:
                fetched = await self._quality_provider()
            except Exception:
                self._log.exception("Quality provider failed during drift evaluation")
                fetched = {}
            report = dict(fetched) if isinstance(fetched, Mapping) else {}
        elif isinstance(provided, Mapping):
            report = dict(provided)
        else:
            report = {}

        drift_section = report.get("drift")
        score: float | None = None
        if isinstance(drift_section, Mapping):
            score = self._coerce_float(drift_section.get("score"))

        prior = self._last_quality_score if self._last_quality_score is not None else score
        delta: float | None = None
        if score is not None and prior is not None:
            delta = max(0.0, score - prior)

        return _QualitySnapshot(report=report, score=score, delta=delta)

    def _build_alerts(
        self,
        quality: _QualitySnapshot,
        integrity: VectorIntegrityReport,
    ) -> list[dict[str, Any]]:
        alerts: list[dict[str, Any]] = []

        quality_alert_active = False
        if (
            quality.score is not None
            and quality.score >= self._quality_alert_threshold
            and (
                self._last_quality_score is None
                or (quality.delta or 0.0) >= self._quality_delta_threshold
                or self._quality_alert_active
            )
        ):
            severity = "critical" if quality.score >= self._quality_critical_threshold else "warning"
            alerts.append(
                {
                    "type": "quality_drift",
                    "severity": severity,
                    "score": quality.score,
                    "delta": quality.delta or 0.0,
                }
            )
            quality_alert_active = True
        elif quality.score is not None and quality.score < self._quality_alert_threshold:
            self._quality_alert_active = False

        drifted_ids = self._coerce_sequence(integrity.get("drifted_ids"))
        max_drift = self._coerce_float(integrity.get("max_drift"), fallback=0.0) or 0.0
        if drifted_ids and max_drift >= self._integrity_alert_threshold:
            severity = "critical" if max_drift >= self._integrity_critical_threshold else "warning"
            alerts.append(
                {
                    "type": "vector_index_drift",
                    "severity": severity,
                    "max_drift": max_drift,
                    "drifted_ids": drifted_ids,
                }
            )

        self._quality_alert_active = quality_alert_active
        return alerts

    async def _emit_alerts(self, summary: Mapping[str, Any]) -> None:
        publisher = self._event_publisher
        if publisher is None or not publisher.enabled:
            return

        alerts = summary.get("alerts")
        alerts_seq = [dict(alert) for alert in alerts] if isinstance(alerts, Sequence) else []
        signature = self._alert_signature(alerts_seq)
        if signature == self._last_alert_signature:
            return

        self._last_alert_signature = signature
        try:
            await publisher.embedding_drift_detected(
                alerts=alerts_seq,
                quality_summary=self._coerce_mapping(summary.get("quality")),
                integrity_summary=self._coerce_mapping(summary.get("integrity")),
                quality_score=self._coerce_float(summary.get("quality_score")),
                quality_delta=self._coerce_float(summary.get("quality_delta")),
                max_drift=self._coerce_float(
                    self._coerce_mapping(summary.get("integrity")).get("max_drift")
                ),
            )
        except Exception:  # pragma: no cover - downstream safety
            self._log.debug("Failed to publish embedding drift event", exc_info=True)

    def _publish_metrics(self, summary: Mapping[str, Any]) -> None:
        metrics = self._metrics
        if metrics is None:
            return

        metrics.publish_embedding_drift(
            quality_score=self._coerce_float(summary.get("quality_score")),
            quality_delta=self._coerce_float(summary.get("quality_delta")),
            integrity_report=self._coerce_mapping(summary.get("integrity")),
            alerts=self._coerce_sequence(summary.get("alerts")),
        )

    def _coerce_integrity_report(self, report: Any) -> dict[str, Any]:
        if hasattr(report, "model_dump"):
            return report.model_dump()
        if isinstance(report, Mapping):
            return dict(report)
        return {}

    def _should_run(self, now: float) -> bool:
        if self._interval == 0:
            return True
        if self._last_check is None:
            return True
        return (now - self._last_check) >= self._interval

    @staticmethod
    def _alert_signature(alerts: Sequence[Mapping[str, Any]]) -> tuple[Any, ...]:
        signature = []
        for alert in alerts:
            drift_ids = tuple(sorted(str(item) for item in EmbeddingDriftMonitor._coerce_sequence(alert.get("drifted_ids"))))
            signature.append(
                (
                    str(alert.get("type")),
                    round(float(alert.get("score", 0.0)), 4) if alert.get("score") is not None else None,
                    round(float(alert.get("delta", 0.0)), 4) if alert.get("delta") is not None else None,
                    round(float(alert.get("max_drift", 0.0)), 4) if alert.get("max_drift") is not None else None,
                    drift_ids,
                )
            )
        return tuple(sorted(signature))

    @staticmethod
    def _coerce_positive_float(value: Any, *, fallback: float) -> float:
        try:
            candidate = float(value)
            if candidate <= 0:
                return fallback
            return candidate
        except (TypeError, ValueError):
            return fallback

    @staticmethod
    def _coerce_positive_int(value: Any, *, fallback: int) -> int:
        try:
            candidate = int(value)
            if candidate < 0:
                return fallback
            return candidate
        except (TypeError, ValueError):
            return fallback

    @staticmethod
    def _coerce_float(value: Any, fallback: float | None = None) -> float | None:
        if value is None:
            return fallback
        try:
            return float(value)
        except (TypeError, ValueError):
            return fallback

    @staticmethod
    def _coerce_mapping(value: Any) -> dict[str, Any]:
        if isinstance(value, Mapping):
            return {str(key): value[key] for key in value}
        return {}

    @staticmethod
    def _coerce_sequence(value: Any) -> list[Any]:
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            return [item for item in value]
        return []


__all__ = ["EmbeddingDriftMonitor"]

