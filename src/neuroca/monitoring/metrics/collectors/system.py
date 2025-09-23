"""System level metrics collector."""

from __future__ import annotations

import logging
import os
import platform
import time
from typing import Optional

import psutil

from neuroca.core.exceptions import MetricsCollectionError
from neuroca.monitoring.metrics.models import Metric, MetricType, MetricUnit

from .base import BaseMetricsCollector

logger = logging.getLogger(__name__)


class SystemMetricsCollector(BaseMetricsCollector):
    """Collect CPU, memory, disk, and process statistics from the host."""

    def __init__(
        self,
        name: str = "system",
        enabled: bool = True,
        collection_interval: float = 60.0,
        metrics_prefix: str = "neuroca",
        include_process_metrics: bool = True,
        process_id: Optional[int] = None,
    ):
        """Initialize a collector for host level telemetry."""
        super().__init__(name, enabled, collection_interval, metrics_prefix)
        self.include_process_metrics = include_process_metrics
        self.process_id = process_id or os.getpid()
        self._process = psutil.Process(self.process_id)

        self.system_labels = {
            "hostname": platform.node(),
            "os": platform.system(),
            "os_version": platform.version(),
            "python_version": platform.python_version(),
        }

        logger.debug("SystemMetricsCollector initialized for process %s", self.process_id)

    def collect(self) -> list[Metric]:
        """Collect system metrics including CPU, memory, disk, and network usage."""
        if not self.should_collect():
            return []

        try:
            metrics = []
            metrics.extend(self._collect_cpu_metrics())
            metrics.extend(self._collect_memory_metrics())
            metrics.extend(self._collect_disk_metrics())

            if self.include_process_metrics:
                metrics.extend(self._collect_process_metrics())

            self.last_collection_time = time.time()
            logger.debug("Collected %s system metrics", len(metrics))
            return metrics

        except Exception as exc:  # noqa: BLE001 - bubble up as MetricsCollectionError
            error_msg = f"Failed to collect system metrics: {exc}".rstrip()
            logger.error(error_msg, exc_info=True)
            raise MetricsCollectionError(error_msg) from exc

    def _collect_cpu_metrics(self) -> list[Metric]:
        """Collect CPU related metrics."""
        metrics: list[Metric] = []

        cpu_percent = psutil.cpu_percent(interval=0.1)
        metrics.append(
            self.create_metric(
                name="cpu.usage.percent",
                value=cpu_percent,
                metric_type=MetricType.GAUGE,
                unit=MetricUnit.PERCENT,
                labels=self.system_labels,
                description="CPU usage percentage (all cores)",
            )
        )

        per_cpu_percent = psutil.cpu_percent(interval=0.1, percpu=True)
        for index, core_percent in enumerate(per_cpu_percent):
            core_labels = {**self.system_labels, "core": str(index)}
            metrics.append(
                self.create_metric(
                    name="cpu.core.usage.percent",
                    value=core_percent,
                    metric_type=MetricType.GAUGE,
                    unit=MetricUnit.PERCENT,
                    labels=core_labels,
                    description=f"CPU usage percentage for core {index}",
                )
            )

        if hasattr(psutil, "getloadavg"):
            load1, load5, load15 = psutil.getloadavg()
            metrics.append(
                self.create_metric(
                    name="cpu.load.1min",
                    value=load1,
                    metric_type=MetricType.GAUGE,
                    labels=self.system_labels,
                    description="CPU load average (1 minute)",
                )
            )
            metrics.append(
                self.create_metric(
                    name="cpu.load.5min",
                    value=load5,
                    metric_type=MetricType.GAUGE,
                    labels=self.system_labels,
                    description="CPU load average (5 minutes)",
                )
            )
            metrics.append(
                self.create_metric(
                    name="cpu.load.15min",
                    value=load15,
                    metric_type=MetricType.GAUGE,
                    labels=self.system_labels,
                    description="CPU load average (15 minutes)",
                )
            )

        return metrics

    def _collect_memory_metrics(self) -> list[Metric]:
        """Collect memory related metrics."""
        metrics: list[Metric] = []

        virtual_memory = psutil.virtual_memory()
        metrics.append(
            self.create_metric(
                name="memory.total",
                value=virtual_memory.total,
                metric_type=MetricType.GAUGE,
                unit=MetricUnit.BYTES,
                labels=self.system_labels,
                description="Total physical memory",
            )
        )
        metrics.append(
            self.create_metric(
                name="memory.available",
                value=virtual_memory.available,
                metric_type=MetricType.GAUGE,
                unit=MetricUnit.BYTES,
                labels=self.system_labels,
                description="Available memory",
            )
        )
        metrics.append(
            self.create_metric(
                name="memory.used",
                value=virtual_memory.used,
                metric_type=MetricType.GAUGE,
                unit=MetricUnit.BYTES,
                labels=self.system_labels,
                description="Used memory",
            )
        )
        metrics.append(
            self.create_metric(
                name="memory.percent",
                value=virtual_memory.percent,
                metric_type=MetricType.GAUGE,
                unit=MetricUnit.PERCENT,
                labels=self.system_labels,
                description="Memory usage percentage",
            )
        )

        swap_memory = psutil.swap_memory()
        metrics.append(
            self.create_metric(
                name="swap.total",
                value=swap_memory.total,
                metric_type=MetricType.GAUGE,
                unit=MetricUnit.BYTES,
                labels=self.system_labels,
                description="Total swap memory",
            )
        )
        metrics.append(
            self.create_metric(
                name="swap.used",
                value=swap_memory.used,
                metric_type=MetricType.GAUGE,
                unit=MetricUnit.BYTES,
                labels=self.system_labels,
                description="Used swap memory",
            )
        )
        metrics.append(
            self.create_metric(
                name="swap.free",
                value=swap_memory.free,
                metric_type=MetricType.GAUGE,
                unit=MetricUnit.BYTES,
                labels=self.system_labels,
                description="Free swap memory",
            )
        )
        metrics.append(
            self.create_metric(
                name="swap.percent",
                value=swap_memory.percent,
                metric_type=MetricType.GAUGE,
                unit=MetricUnit.PERCENT,
                labels=self.system_labels,
                description="Swap usage percentage",
            )
        )

        return metrics

    def _collect_disk_metrics(self) -> list[Metric]:
        """Collect disk related metrics."""
        metrics: list[Metric] = []

        try:
            for partition in psutil.disk_partitions(all=False):
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                except PermissionError:
                    continue

                partition_labels = {**self.system_labels, "device": partition.device}
                metrics.append(
                    self.create_metric(
                        name="disk.partition.total",
                        value=usage.total,
                        metric_type=MetricType.GAUGE,
                        unit=MetricUnit.BYTES,
                        labels=partition_labels,
                        description=f"Total size of disk partition {partition.device}",
                    )
                )
                metrics.append(
                    self.create_metric(
                        name="disk.partition.used",
                        value=usage.used,
                        metric_type=MetricType.GAUGE,
                        unit=MetricUnit.BYTES,
                        labels=partition_labels,
                        description=f"Used space on disk partition {partition.device}",
                    )
                )
                metrics.append(
                    self.create_metric(
                        name="disk.partition.free",
                        value=usage.free,
                        metric_type=MetricType.GAUGE,
                        unit=MetricUnit.BYTES,
                        labels=partition_labels,
                        description=f"Free space on disk partition {partition.device}",
                    )
                )
                metrics.append(
                    self.create_metric(
                        name="disk.partition.percent",
                        value=usage.percent,
                        metric_type=MetricType.GAUGE,
                        unit=MetricUnit.PERCENT,
                        labels=partition_labels,
                        description=f"Disk usage percentage for partition {partition.device}",
                    )
                )

            disk_io = psutil.disk_io_counters(perdisk=True)
            for device, io_stats in disk_io.items():
                device_labels = {**self.system_labels, "device": device}
                metrics.append(
                    self.create_metric(
                        name="disk.io.read_bytes",
                        value=io_stats.read_bytes,
                        metric_type=MetricType.COUNTER,
                        unit=MetricUnit.BYTES,
                        labels=device_labels,
                        description=f"Total bytes read from disk device {device}",
                    )
                )
                metrics.append(
                    self.create_metric(
                        name="disk.io.write_bytes",
                        value=io_stats.write_bytes,
                        metric_type=MetricType.COUNTER,
                        unit=MetricUnit.BYTES,
                        labels=device_labels,
                        description=f"Total bytes written to disk device {device}",
                    )
                )
                metrics.append(
                    self.create_metric(
                        name="disk.io.read_time",
                        value=io_stats.read_time,
                        metric_type=MetricType.COUNTER,
                        unit=MetricUnit.MILLISECONDS,
                        labels=device_labels,
                        description=f"Total time spent reading from disk device {device} (ms)",
                    )
                )
                metrics.append(
                    self.create_metric(
                        name="disk.io.write_time",
                        value=io_stats.write_time,
                        metric_type=MetricType.COUNTER,
                        unit=MetricUnit.MILLISECONDS,
                        labels=device_labels,
                        description=f"Total time spent writing to disk device {device} (ms)",
                    )
                )

        except Exception as exc:  # noqa: BLE001 - non critical disk stats
            logger.warning("Failed to collect detailed disk metrics: %s", exc, exc_info=True)

        return metrics

    def _collect_process_metrics(self) -> list[Metric]:
        """Collect process specific metrics."""
        metrics: list[Metric] = []

        try:
            process_memory = self._process.memory_info()
            metrics.append(
                self.create_metric(
                    name="process.memory.rss",
                    value=process_memory.rss,
                    metric_type=MetricType.GAUGE,
                    unit=MetricUnit.BYTES,
                    labels=self.system_labels,
                    description="Resident set size (physical memory) of the process",
                )
            )
            metrics.append(
                self.create_metric(
                    name="process.memory.vms",
                    value=process_memory.vms,
                    metric_type=MetricType.GAUGE,
                    unit=MetricUnit.BYTES,
                    labels=self.system_labels,
                    description="Virtual memory size of the process",
                )
            )

            cpu_times = self._process.cpu_times()
            metrics.append(
                self.create_metric(
                    name="process.cpu.user",
                    value=cpu_times.user,
                    metric_type=MetricType.COUNTER,
                    unit=MetricUnit.SECONDS,
                    labels=self.system_labels,
                    description="Total user CPU time used by the process",
                )
            )
            metrics.append(
                self.create_metric(
                    name="process.cpu.system",
                    value=cpu_times.system,
                    metric_type=MetricType.COUNTER,
                    unit=MetricUnit.SECONDS,
                    labels=self.system_labels,
                    description="Total system CPU time used by the process",
                )
            )

            io_counters = self._process.io_counters()
            metrics.append(
                self.create_metric(
                    name="process.io.read_bytes",
                    value=io_counters.read_bytes,
                    metric_type=MetricType.COUNTER,
                    unit=MetricUnit.BYTES,
                    labels=self.system_labels,
                    description="Total bytes read by the process",
                )
            )
            metrics.append(
                self.create_metric(
                    name="process.io.write_bytes",
                    value=io_counters.write_bytes,
                    metric_type=MetricType.COUNTER,
                    unit=MetricUnit.BYTES,
                    labels=self.system_labels,
                    description="Total bytes written by the process",
                )
            )

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as exc:
            logger.warning("Failed to collect process metrics for PID %s: %s", self.process_id, exc)

        return metrics
