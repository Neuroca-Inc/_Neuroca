from __future__ import annotations

import asyncio
import statistics
import time
from dataclasses import dataclass
from typing import Any, Dict, List

from .util import call_llm


@dataclass
class LatencyStats:
    count: int
    mean_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float


def _percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    values_sorted = sorted(values)
    k = (len(values_sorted) - 1) * p / 100.0
    f = int(k)
    c = min(f + 1, len(values_sorted) - 1)
    if f == c:
        return values_sorted[f]
    return values_sorted[f] + (values_sorted[c] - values_sorted[f]) * (k - f)


def _stats(samples_ms: List[float]) -> LatencyStats:
    return LatencyStats(
        count=len(samples_ms),
        mean_ms=statistics.mean(samples_ms) if samples_ms else 0.0,
        p50_ms=_percentile(samples_ms, 50),
        p95_ms=_percentile(samples_ms, 95),
        p99_ms=_percentile(samples_ms, 99),
    )


async def run(
    mgr,
    *,
    provider: str,
    model: str,
    runs: int = 20,
    concurrency: int = 2,
    prompt: str = "Say 'ok' concisely.",
    max_tokens: int = 32,
    temperature: float = 0.0,
) -> Dict[str, Any]:
    """
    Latency benchmark.
    - Measures per-request latency under limited concurrency.
    - Reports mean, p50, p95, p99, and error count.
    """
    semaphore = asyncio.Semaphore(concurrency)
    latencies_ms: List[float] = []
    errors = 0

    async def one():
        nonlocal errors
        async with semaphore:
            t0 = time.perf_counter()
            try:
                resp = await call_llm(
                    mgr,
                    prompt=prompt,
                    provider=provider,
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                _ = resp.content
            except Exception:
                errors += 1
            finally:
                t1 = time.perf_counter()
                latencies_ms.append((t1 - t0) * 1000.0)

    await asyncio.gather(*[one() for _ in range(runs)])
    s = _stats(latencies_ms)

    return {
        "name": "latency",
        "runs": runs,
        "concurrency": concurrency,
        "errors": errors,
        "latency_ms": {
            "mean": round(s.mean_ms, 2),
            "p50": round(s.p50_ms, 2),
            "p95": round(s.p95_ms, 2),
            "p99": round(s.p99_ms, 2),
        },
    }