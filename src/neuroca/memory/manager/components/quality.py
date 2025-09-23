"""Quality and drift analysis helpers for the memory manager."""

from __future__ import annotations

import asyncio
from datetime import datetime
import time
from typing import Any, Dict, Iterable, List, Mapping, Optional

from .base import LOGGER


class MemoryManagerQualityMixin:
    """Provide memory quality evaluation and drift monitoring utilities."""

    @property
    def last_quality_report(self) -> Optional[Dict[str, Any]]:
        """Return the cached quality report from the most recent evaluation."""

        report = getattr(self._quality_state, "last_report", None)
        return dict(report) if isinstance(report, dict) else None

    @property
    def last_drift_report(self) -> Optional[Dict[str, Any]]:
        """Return the cached embedding drift evaluation report."""

        report = getattr(self._drift_state, "last_report", None)
        return dict(report) if isinstance(report, dict) else None

    async def evaluate_memory_quality(self, *, limit: int | None = None) -> Dict[str, Any]:
        """Evaluate long-term memory quality and return structured metrics."""

        self._ensure_initialized()

        snapshot = await self._collect_ltm_memories(limit=limit)
        report = self._quality_analyzer.evaluate(snapshot)
        self._quality_state.last_report = report
        evaluated_at = report.get("evaluated_at") if isinstance(report, dict) else None
        if isinstance(evaluated_at, str):
            try:
                self._quality_state.last_evaluated_at = datetime.fromisoformat(
                    evaluated_at
                ).timestamp()
            except ValueError:
                self._quality_state.last_evaluated_at = time.time()
        else:
            self._quality_state.last_evaluated_at = time.time()
        return report

    async def detect_embedding_drift(
        self,
        *,
        quality_report: Mapping[str, Any] | None = None,
        force: bool = False,
        sample_size: int | None = None,
    ) -> Dict[str, Any]:
        """Evaluate embedding drift and return a structured summary."""

        self._ensure_initialized()

        monitor = self._drift_monitor
        if monitor is None:
            return {}

        result = await monitor.run_checks(
            quality_report=quality_report,
            force=force,
            sample_size=sample_size,
        )
        if not result:
            return {}

        self._drift_state.last_report = dict(result)
        checked_at = result.get("checked_at")
        if isinstance(checked_at, str):
            try:
                self._drift_state.last_checked_at = datetime.fromisoformat(
                    checked_at
                ).timestamp()
            except ValueError:
                self._drift_state.last_checked_at = time.time()
        else:
            self._drift_state.last_checked_at = time.time()

        return dict(result)

    async def _collect_ltm_memories(self, limit: int | None = None) -> List[Any]:
        """Gather a snapshot of LTM memories for quality analysis."""

        if self._ltm is None:
            return []

        retrieval_methods = ("list_all", "retrieve_all", "list")
        cache = self._ltm_retrieval_cache
        for method_name in retrieval_methods:
            cached_handler = cache.get(method_name)
            if cached_handler is None and method_name in cache:
                continue

            if cached_handler is not None:
                handler = cached_handler
            else:
                handler = getattr(self._ltm, method_name, None)
                if handler is None:
                    cache[method_name] = None
                    continue

            if not callable(handler):
                LOGGER.debug(
                    "Skipping non-callable retrieval handler %s for LTM snapshot",
                    method_name,
                )
                cache[method_name] = None
                continue

            signature = getattr(handler, "__signature__", None)
            if signature is None and hasattr(handler, "__call__"):
                signature = getattr(handler.__call__, "__signature__", None)
            if signature is not None and signature.parameters:
                LOGGER.debug("Skipping handler %s requiring parameters", method_name)
                cache[method_name] = None
                continue

            try:
                result = handler()
                if asyncio.iscoroutine(result):
                    result = await result
                if isinstance(result, list):
                    sequence = result
                elif isinstance(result, Iterable) and not isinstance(result, (str, bytes)):
                    sequence = list(result)
                else:
                    continue
            except Exception:
                LOGGER.exception("Failed to coerce LTM snapshot from %s", method_name)
                cache[method_name] = None
                continue

            cache[method_name] = handler
            return sequence[: limit] if limit is not None else sequence

        LOGGER.debug(
            "LTM storage does not expose bulk retrieval; skipping quality analysis"
        )
        return []

    def _configure_drift_monitor(self) -> None:
        """Configure the embedding drift monitor for the current backend."""

        backend = None if self._ltm is None else getattr(self._ltm, "_backend", None)
        self._drift_monitor.configure(
            vector_backend=backend,
            metrics=self._metrics,
            event_publisher=self._event_publisher,
            quality_provider=self.evaluate_memory_quality,
        )


__all__ = ["MemoryManagerQualityMixin"]
