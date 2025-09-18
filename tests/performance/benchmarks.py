"""
Performance Benchmarking Module for NeuroCognitive Architecture (NCA)

This module provides comprehensive benchmarking tools to measure and analyze the 
performance of various components of the NCA system. It includes utilities for:
- Memory access and manipulation benchmarks
- Processing speed measurements
- Resource utilization tracking
- Comparative performance analysis
- Benchmark result persistence and visualization

Usage:
    from neuroca.tests.performance.benchmarks import run_benchmark_suite
    
    # Run all benchmarks
    results = run_benchmark_suite()
    
    # Run specific benchmark
    memory_results = run_benchmark('memory_access')
    
    # Run benchmark with custom parameters
    custom_results = run_benchmark('llm_integration', 
                                  iterations=100, 
                                  payload_size=1024)
"""

import asyncio
from asyncio import QueueEmpty
import datetime
import json
import logging
import os
import statistics
import random
import string
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from functools import wraps
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import psutil

from neuroca.memory.backends import BackendType
from neuroca.memory.manager.memory_manager import MemoryManager

# Configure logging
logger = logging.getLogger(__name__)

# Constants
DEFAULT_ITERATIONS = 50
DEFAULT_WARMUP_ITERATIONS = 5
BENCHMARK_RESULTS_DIR = Path("benchmark_results")


@dataclass
class BenchmarkResult:
    """Data class to store benchmark results."""
    name: str
    execution_times: list[float]
    start_time: datetime.datetime
    end_time: datetime.datetime
    parameters: dict[str, Any] = field(default_factory=dict)
    memory_usage: dict[str, float] = field(default_factory=dict)
    cpu_usage: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    
    @property
    def mean_execution_time(self) -> float:
        """Calculate the mean execution time."""
        return statistics.mean(self.execution_times)
    
    @property
    def median_execution_time(self) -> float:
        """Calculate the median execution time."""
        return statistics.median(self.execution_times)
    
    @property
    def std_deviation(self) -> float:
        """Calculate the standard deviation of execution times."""
        return statistics.stdev(self.execution_times) if len(self.execution_times) > 1 else 0
    
    @property
    def min_execution_time(self) -> float:
        """Get the minimum execution time."""
        return min(self.execution_times)
    
    @property
    def max_execution_time(self) -> float:
        """Get the maximum execution time."""
        return max(self.execution_times)
    
    @property
    def total_duration(self) -> float:
        """Calculate the total benchmark duration in seconds."""
        return (self.end_time - self.start_time).total_seconds()
    
    def to_dict(self) -> dict[str, Any]:
        """Convert the benchmark result to a dictionary."""
        result = asdict(self)
        # Add computed properties
        result.update({
            "mean_execution_time": self.mean_execution_time,
            "median_execution_time": self.median_execution_time,
            "std_deviation": self.std_deviation,
            "min_execution_time": self.min_execution_time,
            "max_execution_time": self.max_execution_time,
            "total_duration": self.total_duration
        })
        # Convert datetime objects to ISO format strings
        result["start_time"] = self.start_time.isoformat()
        result["end_time"] = self.end_time.isoformat()
        return result
    
    def save(self, directory: Optional[Path] = None) -> Path:
        """Save benchmark results to a JSON file."""
        if directory is None:
            directory = BENCHMARK_RESULTS_DIR
        
        directory.mkdir(exist_ok=True, parents=True)
        
        timestamp = self.start_time.strftime("%Y%m%d_%H%M%S")
        filename = f"{self.name}_{timestamp}.json"
        filepath = directory / filename
        
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
        
        logger.info(f"Benchmark results saved to {filepath}")
        return filepath


@contextmanager
def measure_time() -> float:
    """Context manager to measure execution time."""
    start_time = time.perf_counter()
    try:
        yield
    finally:
        end_time = time.perf_counter()
        end_time - start_time


@contextmanager
def measure_resources():
    """Context manager to measure CPU and memory usage."""
    process = psutil.Process(os.getpid())

    # Measure before
    mem_before = process.memory_info().rss / 1024 / 1024  # MB
    cpu_percent_before = process.cpu_percent()

    yield

    # Measure after
    mem_after = process.memory_info().rss / 1024 / 1024  # MB
    cpu_percent_after = process.cpu_percent()

    return {
        "memory_usage_mb": mem_after - mem_before,
        "cpu_percent": cpu_percent_after - cpu_percent_before
    }


TIER_ORDER: tuple[str, ...] = (
    MemoryManager.STM_TIER,
    MemoryManager.MTM_TIER,
    MemoryManager.LTM_TIER,
)


def _percentile(values: Sequence[float], percentile: float) -> float:
    """Return the requested percentile using NumPy's percentile implementation."""

    if not values:
        return 0.0

    return float(np.percentile(values, percentile, method="linear"))


def _summarize_latencies(samples: Sequence[float]) -> Dict[str, float]:
    """Summarise latency samples in seconds into millisecond statistics."""

    if not samples:
        return {
            "samples": 0,
            "mean_ms": 0.0,
            "p50_ms": 0.0,
            "p95_ms": 0.0,
            "min_ms": 0.0,
            "max_ms": 0.0,
        }

    latencies_ms = [value * 1000.0 for value in samples]
    return {
        "samples": len(latencies_ms),
        "mean_ms": float(statistics.mean(latencies_ms)),
        "p50_ms": float(_percentile(latencies_ms, 50.0)),
        "p95_ms": float(_percentile(latencies_ms, 95.0)),
        "min_ms": float(min(latencies_ms)),
        "max_ms": float(max(latencies_ms)),
    }


def _summarize_throughput(samples: Sequence[float]) -> Dict[str, float]:
    """Summarise throughput samples (operations per second)."""

    if not samples:
        return {
            "samples": 0,
            "mean_ops_per_sec": 0.0,
            "p50_ops_per_sec": 0.0,
            "p95_ops_per_sec": 0.0,
            "min_ops_per_sec": 0.0,
            "max_ops_per_sec": 0.0,
        }

    return {
        "samples": len(samples),
        "mean_ops_per_sec": float(statistics.mean(samples)),
        "p50_ops_per_sec": float(_percentile(samples, 50.0)),
        "p95_ops_per_sec": float(_percentile(samples, 95.0)),
        "min_ops_per_sec": float(min(samples)),
        "max_ops_per_sec": float(max(samples)),
    }


def _chunked(values: Sequence[str], chunk_size: int) -> Iterable[Sequence[str]]:
    """Yield successive chunks from *values* of size ``chunk_size``."""

    if chunk_size <= 0:
        raise ValueError("chunk_size must be a positive integer")

    for start in range(0, len(values), chunk_size):
        yield values[start:start + chunk_size]


def _generate_memory_content(index: int, length: int, rng: random.Random) -> str:
    """Generate deterministic pseudo-random memory content of ``length`` characters."""

    prefix = f"Baseline memory {index}: "
    remaining = max(0, length - len(prefix))
    if remaining == 0:
        return prefix[:length]

    alphabet = string.ascii_letters + string.digits + " "
    body = "".join(rng.choice(alphabet) for _ in range(remaining))
    return prefix + body


async def _collect_retrieval_latency_baseline(
    num_memories_per_tier: Mapping[str, int],
    retrieval_iterations: int,
    content_length: int,
    random_seed: int,
    randomize_order: bool,
) -> Dict[str, Any]:
    """Populate each tier and measure retrieval latencies."""

    manager = MemoryManager(
        config={"maintenance_interval": 0},
        backend_type=BackendType.MEMORY,
    )
    await manager.initialize()
    rng = random.Random(random_seed)

    try:
        memory_counts = {
            tier: max(0, int(num_memories_per_tier.get(tier, 0)))
            for tier in TIER_ORDER
        }

        ids_by_tier: Dict[str, list[str]] = {tier: [] for tier in TIER_ORDER}

        for tier, count in memory_counts.items():
            for index in range(count):
                content = _generate_memory_content(index, content_length, rng)
                memory_id = await manager.add_memory(
                    content,
                    importance=0.65,
                    metadata={"source": "performance_baseline"},
                    tags=["baseline", tier],
                    initial_tier=tier,
                )
                ids_by_tier[tier].append(memory_id)

        # Warm up each tier to ensure caches and strength models are initialised
        for tier, identifiers in ids_by_tier.items():
            for memory_id in identifiers:
                await manager.retrieve_memory(memory_id, tier=tier)

        latencies_by_tier: Dict[str, list[float]] = {tier: [] for tier in TIER_ORDER}
        aggregate_latencies: list[float] = []

        iterations = max(1, retrieval_iterations)
        for tier, identifiers in ids_by_tier.items():
            if not identifiers:
                continue

            for _ in range(iterations):
                ordered = list(identifiers)
                if randomize_order and len(ordered) > 1:
                    rng.shuffle(ordered)

                for memory_id in ordered:
                    start = time.perf_counter()
                    item = await manager.retrieve_memory(memory_id, tier=tier)
                    if item is None:
                        raise RuntimeError(
                            f"Memory {memory_id} missing from tier {tier} during baseline collection"
                        )

                    duration = time.perf_counter() - start
                    latencies_by_tier[tier].append(duration)
                    aggregate_latencies.append(duration)

        tier_stats = {
            tier: _summarize_latencies(latencies_by_tier.get(tier, []))
            for tier in TIER_ORDER
        }

        return {
            "tiers": tier_stats,
            "aggregate": _summarize_latencies(aggregate_latencies),
            "memory_counts": memory_counts,
            "iterations": iterations,
            "randomized": bool(randomize_order),
        }
    finally:
        await manager.shutdown()


def run_retrieval_latency_baseline(
    *,
    num_memories_per_tier: Mapping[str, int] | None = None,
    retrieval_iterations: int = 3,
    content_length: int = 256,
    random_seed: int = 42,
    randomize_order: bool = True,
) -> Dict[str, Any]:
    """Synchronously execute the retrieval latency baseline benchmark."""

    payload = num_memories_per_tier or {
        MemoryManager.STM_TIER: 120,
        MemoryManager.MTM_TIER: 120,
        MemoryManager.LTM_TIER: 120,
    }

    return asyncio.run(
        _collect_retrieval_latency_baseline(
            payload,
            retrieval_iterations,
            max(32, int(content_length)),
            random_seed,
            randomize_order,
        )
    )


async def _collect_consolidation_throughput_baseline(
    total_memories: int,
    batch_size: int,
    content_length: int,
    random_seed: int,
) -> Dict[str, Any]:
    """Populate STM and measure consolidation throughput across tiers."""

    manager = MemoryManager(
        config={"maintenance_interval": 0},
        backend_type=BackendType.MEMORY,
    )
    await manager.initialize()
    rng = random.Random(random_seed)

    try:
        stm_ids: list[str] = []
        for index in range(total_memories):
            content = _generate_memory_content(index, content_length, rng)
            memory_id = await manager.add_memory(
                content,
                importance=0.75,
                metadata={"source": "performance_baseline"},
                tags=["baseline", MemoryManager.STM_TIER],
                initial_tier=MemoryManager.STM_TIER,
            )
            stm_ids.append(memory_id)

        if len(stm_ids) > 1:
            rng.shuffle(stm_ids)

        stage_samples: Dict[str, list[float]] = {
            "stm_to_mtm": [],
            "mtm_to_ltm": [],
        }

        mtm_ids: list[str] = []
        for chunk in _chunked(stm_ids, batch_size):
            if not chunk:
                continue

            start = time.perf_counter()
            produced: list[str] = []
            for memory_id in chunk:
                new_id = await manager.consolidate_memory(
                    memory_id,
                    MemoryManager.STM_TIER,
                    MemoryManager.MTM_TIER,
                )
                if new_id:
                    produced.append(new_id)

            duration = time.perf_counter() - start
            if duration > 0 and produced:
                stage_samples["stm_to_mtm"].append(len(produced) / duration)

            mtm_ids.extend(produced)

        stage_one_completed = len(mtm_ids)

        if len(mtm_ids) > 1:
            rng.shuffle(mtm_ids)

        ltm_ids: list[str] = []
        for chunk in _chunked(mtm_ids, batch_size):
            if not chunk:
                continue

            start = time.perf_counter()
            produced: list[str] = []
            for memory_id in chunk:
                new_id = await manager.consolidate_memory(
                    memory_id,
                    MemoryManager.MTM_TIER,
                    MemoryManager.LTM_TIER,
                )
                if new_id:
                    produced.append(new_id)

            duration = time.perf_counter() - start
            if duration > 0 and produced:
                stage_samples["mtm_to_ltm"].append(len(produced) / duration)

            ltm_ids.extend(produced)

        aggregate_samples = (
            stage_samples["stm_to_mtm"] + stage_samples["mtm_to_ltm"]
        )

        return {
            "stages": {
                stage: _summarize_throughput(values)
                for stage, values in stage_samples.items()
            },
            "aggregate": _summarize_throughput(aggregate_samples),
            "batch_size": batch_size,
            "total_memories": total_memories,
            "completed": {
                "stm_to_mtm": stage_one_completed,
                "mtm_to_ltm": len(ltm_ids),
            },
        }
    finally:
        await manager.shutdown()


def run_consolidation_throughput_baseline(
    *,
    total_memories: int = 240,
    batch_size: int = 12,
    content_length: int = 256,
    random_seed: int = 99,
) -> Dict[str, Any]:
    """Synchronously execute the consolidation throughput baseline benchmark."""

    if total_memories <= 0:
        raise ValueError("total_memories must be a positive integer")
    if batch_size <= 0:
        raise ValueError("batch_size must be a positive integer")

    return asyncio.run(
        _collect_consolidation_throughput_baseline(
            total_memories,
            batch_size,
            max(32, int(content_length)),
            random_seed,
        )
    )


async def _execute_high_concurrency_stress_scenario(
    *,
    concurrent_workers: int,
    operations_per_worker: int,
    preloaded_memories: Mapping[str, int],
    content_length: int,
    random_seed: int,
) -> Dict[str, Any]:
    """Drive concurrent ingestion, retrieval, and consolidation across tiers."""

    manager = MemoryManager(
        config={"maintenance_interval": 0},
        backend_type=BackendType.MEMORY,
    )
    await manager.initialize()

    preloaded_counts = {
        tier: max(0, int(preloaded_memories.get(tier, 0)))
        for tier in TIER_ORDER
    }
    total_seed = sum(preloaded_counts.values())

    tier_state: Dict[str, Dict[str, Any]] = {
        MemoryManager.STM_TIER: {
            "ids": set(),
            "lock": asyncio.Lock(),
            "queue": asyncio.Queue(),
        },
        MemoryManager.MTM_TIER: {
            "ids": set(),
            "lock": asyncio.Lock(),
            "queue": asyncio.Queue(),
        },
        MemoryManager.LTM_TIER: {
            "ids": set(),
            "lock": asyncio.Lock(),
            "queue": None,
        },
    }

    async def register_new_id(tier: str, memory_id: str, enqueue: bool = False) -> None:
        async with tier_state[tier]["lock"]:
            tier_state[tier]["ids"].add(memory_id)

        queue = tier_state[tier].get("queue")
        if enqueue and queue is not None:
            queue.put_nowait(memory_id)

    async def remove_id(tier: str, memory_id: str) -> None:
        async with tier_state[tier]["lock"]:
            tier_state[tier]["ids"].discard(memory_id)

    async def sample_id(tier: str, rng_instance: random.Random) -> Optional[str]:
        async with tier_state[tier]["lock"]:
            if not tier_state[tier]["ids"]:
                return None
            choices = tuple(tier_state[tier]["ids"])

        return rng_instance.choice(choices)

    seed_rng = random.Random(random_seed)
    seed_index = 0
    for tier in TIER_ORDER:
        count = preloaded_counts.get(tier, 0)
        for _ in range(count):
            content = _generate_memory_content(seed_index, content_length, seed_rng)
            seed_index += 1
            memory_id = await manager.add_memory(
                content,
                importance=0.6,
                metadata={"source": "concurrency_stress_seed", "tier": tier},
                tags=["stress_seed", tier],
                initial_tier=tier,
            )
            await register_new_id(
                tier,
                memory_id,
                enqueue=tier != MemoryManager.LTM_TIER,
            )

    operation_keys: tuple[str, ...] = (
        "ingest_stm",
        "promote_stm_to_mtm",
        "promote_mtm_to_ltm",
        "retrieve_stm",
        "retrieve_mtm",
        "retrieve_ltm",
    )

    start_time = time.perf_counter()

    async def worker(
        worker_index: int,
    ) -> tuple[dict[str, int], dict[str, list[float]], list[dict[str, Any]]]:
        local_counts: Dict[str, int] = {key: 0 for key in operation_keys}
        local_latencies: Dict[str, list[float]] = {key: [] for key in operation_keys}
        local_errors: list[dict[str, Any]] = []
        local_rng = random.Random(random_seed + worker_index + 1)

        async def do_ingest(iteration_index: int) -> bool:
            content_index = total_seed + worker_index * operations_per_worker + iteration_index
            content = _generate_memory_content(content_index, content_length, local_rng)
            start = time.perf_counter()
            try:
                memory_id = await manager.add_memory(
                    content,
                    importance=0.55,
                    metadata={
                        "source": "concurrency_stress",
                        "worker": worker_index,
                    },
                    tags=["stress", f"worker:{worker_index}"],
                    initial_tier=MemoryManager.STM_TIER,
                )
            except Exception as exc:  # pragma: no cover - surfaced via error reporting
                local_errors.append(
                    {
                        "worker": worker_index,
                        "operation": "ingest_stm",
                        "error": str(exc),
                    }
                )
                return False

            duration = time.perf_counter() - start
            local_counts["ingest_stm"] += 1
            local_latencies["ingest_stm"].append(duration)
            await register_new_id(MemoryManager.STM_TIER, memory_id, enqueue=True)
            return True

        async def do_promote(source: str, target: str, op_key: str) -> bool:
            queue = tier_state[source]["queue"]
            if queue is None:
                return False

            try:
                memory_id = queue.get_nowait()
            except QueueEmpty:
                return False

            start = time.perf_counter()
            try:
                new_id = await manager.consolidate_memory(memory_id, source, target)
            except Exception as exc:  # pragma: no cover - surfaced via error reporting
                local_errors.append(
                    {
                        "worker": worker_index,
                        "operation": op_key,
                        "memory_id": memory_id,
                        "error": str(exc),
                    }
                )
                queue.put_nowait(memory_id)
                return False

            duration = time.perf_counter() - start
            local_counts[op_key] += 1
            local_latencies[op_key].append(duration)

            await remove_id(source, memory_id)
            if new_id:
                await register_new_id(
                    target,
                    new_id,
                    enqueue=target != MemoryManager.LTM_TIER,
                )
            return True

        async def do_retrieve(tier: str) -> bool:
            memory_id = await sample_id(tier, local_rng)
            if memory_id is None:
                return False

            start = time.perf_counter()
            try:
                item = await manager.retrieve_memory(memory_id, tier=tier)
            except Exception as exc:  # pragma: no cover - surfaced via error reporting
                local_errors.append(
                    {
                        "worker": worker_index,
                        "operation": f"retrieve_{tier}",
                        "memory_id": memory_id,
                        "error": str(exc),
                    }
                )
                return False

            if item is None:
                local_errors.append(
                    {
                        "worker": worker_index,
                        "operation": f"retrieve_{tier}",
                        "memory_id": memory_id,
                        "error": "memory_missing",
                    }
                )
                return False

            duration = time.perf_counter() - start
            key = f"retrieve_{tier}"
            local_counts[key] += 1
            local_latencies[key].append(duration)
            return True

        for iteration_index in range(operations_per_worker):
            action = local_rng.random()
            executed = False

            if action < 0.4:
                executed = await do_ingest(iteration_index)
            elif action < 0.65:
                executed = await do_promote(
                    MemoryManager.STM_TIER,
                    MemoryManager.MTM_TIER,
                    "promote_stm_to_mtm",
                )
            elif action < 0.85:
                executed = await do_promote(
                    MemoryManager.MTM_TIER,
                    MemoryManager.LTM_TIER,
                    "promote_mtm_to_ltm",
                )
            else:
                tiers = list(TIER_ORDER)
                local_rng.shuffle(tiers)
                for tier in tiers:
                    if await do_retrieve(tier):
                        executed = True
                        break

            if not executed:
                await do_ingest(iteration_index)

            await asyncio.sleep(0)

        return local_counts, local_latencies, local_errors

    result: Dict[str, Any]
    try:
        workers = [asyncio.create_task(worker(index)) for index in range(concurrent_workers)]
        worker_results = await asyncio.gather(*workers)
        total_duration = time.perf_counter() - start_time

        aggregate_counts: Dict[str, int] = {key: 0 for key in operation_keys}
        aggregate_latencies: Dict[str, list[float]] = {key: [] for key in operation_keys}
        errors: list[dict[str, Any]] = []

        for counts, latencies, worker_errors in worker_results:
            for key, value in counts.items():
                aggregate_counts[key] += value
            for key, samples in latencies.items():
                aggregate_latencies[key].extend(samples)
            errors.extend(worker_errors)

        total_operations = sum(aggregate_counts.values())

        result = {
            "parameters": {
                "concurrent_workers": concurrent_workers,
                "operations_per_worker": operations_per_worker,
                "preloaded_memories": preloaded_counts,
                "content_length": content_length,
                "random_seed": random_seed,
            },
            "operation_counts": aggregate_counts,
            "latency_ms": {
                key: _summarize_latencies(aggregate_latencies[key])
                for key in operation_keys
            },
            "errors": errors,
            "workers": concurrent_workers,
            "total_operations": total_operations,
            "total_duration_seconds": total_duration,
            "aggregate_throughput_ops_per_sec": (
                total_operations / total_duration if total_duration > 0 else 0.0
            ),
        }
    finally:
        await manager.shutdown()

    return result


def run_high_concurrency_stress_scenario(
    *,
    concurrent_workers: int = 24,
    operations_per_worker: int = 40,
    preloaded_memories: Mapping[str, int] | None = None,
    content_length: int = 256,
    random_seed: int = 2024,
) -> Dict[str, Any]:
    """Synchronously execute the high-concurrency stress scenario."""

    if concurrent_workers <= 0:
        raise ValueError("concurrent_workers must be a positive integer")
    if operations_per_worker <= 0:
        raise ValueError("operations_per_worker must be a positive integer")

    base_preload = {
        MemoryManager.STM_TIER: 180,
        MemoryManager.MTM_TIER: 120,
        MemoryManager.LTM_TIER: 80,
    }

    payload = {tier: base_preload.get(tier, 0) for tier in TIER_ORDER}
    if preloaded_memories:
        for tier in TIER_ORDER:
            if tier in preloaded_memories:
                payload[tier] = max(0, int(preloaded_memories[tier]))

    return asyncio.run(
        _execute_high_concurrency_stress_scenario(
            concurrent_workers=concurrent_workers,
            operations_per_worker=operations_per_worker,
            preloaded_memories=payload,
            content_length=max(32, int(content_length)),
            random_seed=random_seed,
        )
    )


def benchmark(func=None, *, iterations=DEFAULT_ITERATIONS, warmup=DEFAULT_WARMUP_ITERATIONS,
              parameters=None, metadata=None):
    """
    Decorator to benchmark a function.
    
    Args:
        func: The function to benchmark
        iterations: Number of iterations to run
        warmup: Number of warmup iterations (not included in results)
        parameters: Additional parameters to include in the benchmark result
        metadata: Additional metadata to include in the benchmark result
    
    Returns:
        Decorated function that returns a BenchmarkResult
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            func_name = func.__name__
            logger.info(f"Starting benchmark: {func_name}")
            
            # Initialize result data
            execution_times = []
            memory_usage = {}
            cpu_usage = {}
            start_time = datetime.datetime.now()
            
            # Perform warmup iterations
            logger.debug(f"Performing {warmup} warmup iterations")
            for _ in range(warmup):
                func(*args, **kwargs)
            
            # Perform benchmark iterations
            logger.info(f"Running {iterations} benchmark iterations")
            for i in range(iterations):
                # Measure execution time
                iteration_start = time.perf_counter()
                
                # Measure resource usage
                process = psutil.Process(os.getpid())
                mem_before = process.memory_info().rss / 1024 / 1024  # MB
                cpu_before = process.cpu_percent(interval=None)
                
                # Execute function
                result = func(*args, **kwargs)
                
                # Measure resource usage after execution
                mem_after = process.memory_info().rss / 1024 / 1024  # MB
                cpu_after = process.cpu_percent(interval=None)
                
                # Record measurements
                iteration_end = time.perf_counter()
                execution_time = iteration_end - iteration_start
                execution_times.append(execution_time)
                
                memory_usage[f"iteration_{i}"] = mem_after - mem_before
                cpu_usage[f"iteration_{i}"] = cpu_after - cpu_before
                
                logger.debug(f"Iteration {i+1}/{iterations}: {execution_time:.6f}s")
            
            end_time = datetime.datetime.now()
            
            # Create benchmark result
            benchmark_result = BenchmarkResult(
                name=func_name,
                execution_times=execution_times,
                start_time=start_time,
                end_time=end_time,
                parameters=parameters or {},
                memory_usage=memory_usage,
                cpu_usage=cpu_usage,
                metadata=metadata or {}
            )
            
            # Log summary
            logger.info(f"Benchmark complete: {func_name}")
            logger.info(f"Mean execution time: {benchmark_result.mean_execution_time:.6f}s")
            logger.info(f"Median execution time: {benchmark_result.median_execution_time:.6f}s")
            logger.info(f"Min/Max execution time: {benchmark_result.min_execution_time:.6f}s / {benchmark_result.max_execution_time:.6f}s")
            
            return result, benchmark_result
        
        return wrapper
    
    if func is None:
        return decorator
    return decorator(func)


def run_benchmark(benchmark_name: str, **kwargs) -> BenchmarkResult:
    """
    Run a specific benchmark by name.
    
    Args:
        benchmark_name: Name of the benchmark to run
        **kwargs: Additional parameters to pass to the benchmark
    
    Returns:
        BenchmarkResult object containing the results
    
    Raises:
        ValueError: If the benchmark name is not recognized
    """
    benchmark_registry = {
        "memory_access": benchmark_memory_access,
        "memory_tier_comparison": benchmark_memory_tier_comparison,
        "llm_integration": benchmark_llm_integration,
        "cognitive_processing": benchmark_cognitive_processing,
        "system_throughput": benchmark_system_throughput,
        "consolidation_throughput": benchmark_system_throughput,
        "concurrency_stress": benchmark_concurrency_stress,
    }
    
    if benchmark_name not in benchmark_registry:
        raise ValueError(f"Unknown benchmark: {benchmark_name}. Available benchmarks: {list(benchmark_registry.keys())}")
    
    logger.info(f"Running benchmark: {benchmark_name}")
    _, result = benchmark_registry[benchmark_name](**kwargs)
    return result


def run_benchmark_suite(benchmarks: Optional[list[str]] = None, 
                        save_results: bool = True,
                        generate_report: bool = True) -> dict[str, BenchmarkResult]:
    """
    Run a suite of benchmarks and collect their results.
    
    Args:
        benchmarks: List of benchmark names to run. If None, runs all benchmarks.
        save_results: Whether to save results to disk
        generate_report: Whether to generate a report of the results
    
    Returns:
        Dictionary mapping benchmark names to their results
    """
    available_benchmarks = [
        "memory_access",
        "memory_tier_comparison",
        "llm_integration",
        "cognitive_processing",
        "consolidation_throughput",
        "concurrency_stress",
    ]

    benchmarks_to_run = benchmarks or available_benchmarks
    valid_benchmarks = set(available_benchmarks) | {"system_throughput"}

    # Validate benchmark names
    for benchmark in benchmarks_to_run:
        if benchmark not in valid_benchmarks:
            raise ValueError(
                f"Unknown benchmark: {benchmark}. Available benchmarks: {sorted(valid_benchmarks)}"
            )
    
    logger.info(f"Running benchmark suite with {len(benchmarks_to_run)} benchmarks")
    
    results = {}
    for benchmark_name in benchmarks_to_run:
        try:
            result = run_benchmark(benchmark_name)
            results[benchmark_name] = result
            
            if save_results:
                result.save()
                
        except Exception as e:
            logger.error(f"Error running benchmark {benchmark_name}: {str(e)}")
            logger.exception(e)
    
    if generate_report and results:
        generate_benchmark_report(results)
    
    return results


def generate_benchmark_report(results: dict[str, BenchmarkResult], 
                             output_dir: Optional[Path] = None) -> Path:
    """
    Generate a comprehensive report from benchmark results.
    
    Args:
        results: Dictionary mapping benchmark names to their results
        output_dir: Directory to save the report. If None, uses BENCHMARK_RESULTS_DIR.
    
    Returns:
        Path to the generated report
    """
    if output_dir is None:
        output_dir = BENCHMARK_RESULTS_DIR
    
    output_dir.mkdir(exist_ok=True, parents=True)
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = output_dir / f"benchmark_report_{timestamp}.html"
    
    # Create a DataFrame for easier analysis
    data = []
    for name, result in results.items():
        row = {
            "Benchmark": name,
            "Mean (s)": result.mean_execution_time,
            "Median (s)": result.median_execution_time,
            "Min (s)": result.min_execution_time,
            "Max (s)": result.max_execution_time,
            "Std Dev": result.std_deviation,
            "Total Duration (s)": result.total_duration,
        }
        data.append(row)
    
    df = pd.DataFrame(data)
    
    # Generate HTML report
    with open(report_path, 'w') as f:
        f.write("<html><head><title>NeuroCognitive Architecture Benchmark Report</title>")
        f.write("<style>body{font-family:Arial,sans-serif;margin:20px;}")
        f.write("table{border-collapse:collapse;width:100%;}")
        f.write("th,td{border:1px solid #ddd;padding:8px;text-align:left;}")
        f.write("th{background-color:#f2f2f2;}")
        f.write("tr:nth-child(even){background-color:#f9f9f9;}")
        f.write("h1,h2{color:#333;}</style></head><body>")
        f.write("<h1>NeuroCognitive Architecture Benchmark Report</h1>")
        f.write(f"<p>Generated on: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>")
        
        # Summary table
        f.write("<h2>Summary</h2>")
        f.write(df.to_html(index=False))
        
        # Individual benchmark details
        f.write("<h2>Detailed Results</h2>")
        for name, result in results.items():
            f.write(f"<h3>{name}</h3>")
            f.write("<table>")
            for key, value in result.to_dict().items():
                if key == "execution_times":
                    continue  # Skip the raw execution times
                f.write(f"<tr><th>{key}</th><td>{value}</td></tr>")
            f.write("</table>")
            
            # Add execution time distribution plot
            plt.figure(figsize=(10, 6))
            plt.hist(result.execution_times, bins=20, alpha=0.7)
            plt.title(f"{name} - Execution Time Distribution")
            plt.xlabel("Execution Time (s)")
            plt.ylabel("Frequency")
            plt.grid(True, alpha=0.3)
            
            plot_path = output_dir / f"{name}_distribution_{timestamp}.png"
            plt.savefig(plot_path)
            plt.close()
            
            f.write(f"<img src='{plot_path.name}' alt='Execution Time Distribution' width='800'>")
        
        f.write("</body></html>")
    
    logger.info(f"Benchmark report generated at {report_path}")
    return report_path


def compare_benchmarks(benchmark_results: list[BenchmarkResult], 
                      metric: str = "mean_execution_time",
                      output_path: Optional[Path] = None) -> Optional[Path]:
    """
    Compare multiple benchmark results and generate a comparison visualization.
    
    Args:
        benchmark_results: List of benchmark results to compare
        metric: The metric to compare (e.g., "mean_execution_time", "median_execution_time")
        output_path: Path to save the comparison visualization. If None, displays the plot.
    
    Returns:
        Path to the saved visualization if output_path is provided, None otherwise
    """
    if not benchmark_results:
        raise ValueError("No benchmark results provided for comparison")
    
    # Extract data for comparison
    names = [result.name for result in benchmark_results]
    values = []
    
    for result in benchmark_results:
        if metric == "mean_execution_time":
            values.append(result.mean_execution_time)
        elif metric == "median_execution_time":
            values.append(result.median_execution_time)
        elif metric == "min_execution_time":
            values.append(result.min_execution_time)
        elif metric == "max_execution_time":
            values.append(result.max_execution_time)
        elif metric == "std_deviation":
            values.append(result.std_deviation)
        else:
            raise ValueError(f"Unknown metric: {metric}")
    
    # Create comparison plot
    plt.figure(figsize=(12, 8))
    bars = plt.bar(names, values, alpha=0.7)
    
    # Add value labels on top of bars
    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height + 0.001,
                f'{height:.6f}',
                ha='center', va='bottom', rotation=0)
    
    plt.title(f"Benchmark Comparison - {metric.replace('_', ' ').title()}")
    plt.xlabel("Benchmark")
    plt.ylabel(f"{metric.replace('_', ' ').title()} (seconds)")
    plt.grid(True, alpha=0.3)
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    
    if output_path:
        plt.savefig(output_path)
        plt.close()
        return output_path
    else:
        plt.show()
        plt.close()
        return None


# Example benchmark implementations
@benchmark
def benchmark_memory_access(data_size: int = 1000000, access_pattern: str = "sequential"):
    """
    Benchmark memory access patterns.
    
    Args:
        data_size: Size of the data to access
        access_pattern: Pattern of access ("sequential", "random", "strided")
    
    Returns:
        Benchmark results
    """
    logger.info(f"Running memory access benchmark with data_size={data_size}, pattern={access_pattern}")
    
    # Create test data
    data = list(range(data_size))
    result = 0
    
    if access_pattern == "sequential":
        # Sequential access
        for i in range(data_size):
            result += data[i]
    elif access_pattern == "random":
        # Random access
        import random
        indices = [random.randint(0, data_size-1) for _ in range(data_size)]
        for idx in indices:
            result += data[idx]
    elif access_pattern == "strided":
        # Strided access
        stride = 16
        for i in range(0, data_size, stride):
            result += data[i]
    else:
        raise ValueError(f"Unknown access pattern: {access_pattern}")
    
    return result


@benchmark(
    iterations=1,
    warmup=0,
    parameters={"benchmark": "retrieval_latency"},
)
def benchmark_memory_tier_comparison(
    stm_memories: int = 120,
    mtm_memories: int = 120,
    ltm_memories: int = 120,
    retrieval_iterations: int = 3,
    content_length: int = 256,
    random_seed: int = 42,
    randomize_order: bool = True,
):
    """Measure retrieval latency across STM, MTM, and LTM tiers."""

    logger.info(
        "Running retrieval latency baseline: stm=%s, mtm=%s, ltm=%s, iterations=%s",
        stm_memories,
        mtm_memories,
        ltm_memories,
        retrieval_iterations,
    )

    configuration = {
        MemoryManager.STM_TIER: stm_memories,
        MemoryManager.MTM_TIER: mtm_memories,
        MemoryManager.LTM_TIER: ltm_memories,
    }

    return run_retrieval_latency_baseline(
        num_memories_per_tier=configuration,
        retrieval_iterations=retrieval_iterations,
        content_length=content_length,
        random_seed=random_seed,
        randomize_order=randomize_order,
    )


@benchmark
def benchmark_llm_integration(model_size: str = "small", query_complexity: str = "medium", batch_size: int = 1):
    """
    Benchmark LLM integration performance.
    
    Args:
        model_size: Size of the model to simulate ("small", "medium", "large")
        query_complexity: Complexity of the queries ("simple", "medium", "complex")
        batch_size: Number of queries to process in a batch
    
    Returns:
        Benchmark results
    """
    logger.info(f"Running LLM integration benchmark: {model_size}, {query_complexity}, batch_size={batch_size}")
    
    # This is a placeholder implementation
    # In a real implementation, this would interact with actual LLM integrations
    
    # Simulate different model sizes with different processing times
    if model_size == "small":
        base_processing_time = 0.01
    elif model_size == "medium":
        base_processing_time = 0.05
    elif model_size == "large":
        base_processing_time = 0.1
    else:
        raise ValueError(f"Unknown model size: {model_size}")
    
    # Simulate different query complexities
    if query_complexity == "simple":
        complexity_factor = 1
    elif query_complexity == "medium":
        complexity_factor = 2
    elif query_complexity == "complex":
        complexity_factor = 4
    else:
        raise ValueError(f"Unknown query complexity: {query_complexity}")
    
    # Simulate processing
    processing_time = base_processing_time * complexity_factor * batch_size
    time.sleep(processing_time)  # Simulate the processing time
    
    return {
        "model_size": model_size,
        "query_complexity": query_complexity,
        "batch_size": batch_size,
        "simulated_processing_time": processing_time
    }


@benchmark
def benchmark_cognitive_processing(complexity: str = "medium", parallel: bool = False, iterations: int = 100):
    """
    Benchmark cognitive processing capabilities.
    
    Args:
        complexity: Complexity of the cognitive processing ("simple", "medium", "complex")
        parallel: Whether to simulate parallel processing
        iterations: Number of processing iterations
    
    Returns:
        Benchmark results
    """
    logger.info(f"Running cognitive processing benchmark: {complexity}, parallel={parallel}, iterations={iterations}")
    
    # This is a placeholder implementation
    # In a real implementation, this would interact with actual cognitive processing components
    
    # Simulate different complexities
    if complexity == "simple":
        operations_per_iteration = 10
    elif complexity == "medium":
        operations_per_iteration = 100
    elif complexity == "complex":
        operations_per_iteration = 1000
    else:
        raise ValueError(f"Unknown complexity: {complexity}")
    
    result = 0
    
    if parallel and complexity != "simple":
        # Simulate parallel processing
        from concurrent.futures import ThreadPoolExecutor
        
        def process_chunk(chunk_size):
            chunk_result = 0
            for _ in range(chunk_size):
                # Simulate some computation
                chunk_result += sum(i * i for i in range(100))
            return chunk_result
        
        # Divide work into chunks
        chunk_size = operations_per_iteration // 4
        chunks = [chunk_size] * 4
        
        with ThreadPoolExecutor(max_workers=4) as executor:
            chunk_results = list(executor.map(process_chunk, chunks))
            result = sum(chunk_results)
    else:
        # Sequential processing
        for _ in range(iterations):
            for _ in range(operations_per_iteration):
                # Simulate some computation
                result += sum(i * i for i in range(100))
    
    return {
        "complexity": complexity,
        "parallel": parallel,
        "iterations": iterations,
        "result": result
    }


@benchmark(
    iterations=1,
    warmup=0,
    parameters={"benchmark": "consolidation_throughput"},
)
def benchmark_system_throughput(
    total_memories: int = 240,
    batch_size: int = 12,
    content_length: int = 256,
    random_seed: int = 99,
):
    """Measure STM→MTM→LTM consolidation throughput using the live manager."""

    logger.info(
        "Running consolidation throughput baseline: memories=%s, batch_size=%s",
        total_memories,
        batch_size,
    )

    return run_consolidation_throughput_baseline(
        total_memories=total_memories,
        batch_size=batch_size,
        content_length=content_length,
        random_seed=random_seed,
    )


@benchmark(
    iterations=1,
    warmup=0,
    parameters={"benchmark": "concurrency_stress"},
)
def benchmark_concurrency_stress(
    concurrent_workers: int = 16,
    operations_per_worker: int = 30,
    preloaded_stm: int = 96,
    preloaded_mtm: int = 64,
    preloaded_ltm: int = 48,
    content_length: int = 256,
    random_seed: int = 1337,
):
    """Exercise the manager with concurrent ingestion, retrieval, and consolidation."""

    logger.info(
        "Running concurrency stress benchmark: workers=%s, operations=%s",
        concurrent_workers,
        operations_per_worker,
    )

    payload = {
        MemoryManager.STM_TIER: preloaded_stm,
        MemoryManager.MTM_TIER: preloaded_mtm,
        MemoryManager.LTM_TIER: preloaded_ltm,
    }

    return run_high_concurrency_stress_scenario(
        concurrent_workers=concurrent_workers,
        operations_per_worker=operations_per_worker,
        preloaded_memories=payload,
        content_length=content_length,
        random_seed=random_seed,
    )


if __name__ == "__main__":
    # Configure logging when run directly
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run all benchmarks
    results = run_benchmark_suite()
    
    # Print summary
    print("\nBenchmark Summary:")
    for name, result in results.items():
        print(f"{name}: Mean={result.mean_execution_time:.6f}s, Median={result.median_execution_time:.6f}s")