from __future__ import annotations

from tests.performance.benchmarks import (
    run_consolidation_throughput_baseline,
    run_retrieval_latency_baseline,
    run_high_concurrency_stress_scenario,
)


def test_retrieval_latency_baseline_produces_percentiles() -> None:
    result = run_retrieval_latency_baseline(
        num_memories_per_tier={
            "stm": 4,
            "mtm": 3,
            "ltm": 2,
        },
        retrieval_iterations=1,
        content_length=64,
        random_seed=123,
        randomize_order=False,
    )

    assert set(result["tiers"].keys()) == {"stm", "mtm", "ltm"}

    total_samples = 0
    for tier, metrics in result["tiers"].items():
        expected_count = result["memory_counts"].get(tier, 0)
        if expected_count == 0:
            assert metrics["samples"] == 0
            continue

        assert metrics["samples"] > 0
        assert metrics["p95_ms"] >= metrics["p50_ms"] >= 0.0
        assert metrics["max_ms"] >= metrics["min_ms"] >= 0.0
        total_samples += metrics["samples"]

    aggregate = result["aggregate"]
    assert aggregate["samples"] == total_samples
    assert aggregate["p95_ms"] >= aggregate["p50_ms"] >= 0.0


def test_consolidation_throughput_baseline_reports_stages() -> None:
    result = run_consolidation_throughput_baseline(
        total_memories=12,
        batch_size=3,
        content_length=64,
        random_seed=321,
    )

    assert set(result["stages"].keys()) == {"stm_to_mtm", "mtm_to_ltm"}

    stage_samples = 0
    for metrics in result["stages"].values():
        assert metrics["samples"] > 0
        assert metrics["p95_ops_per_sec"] >= metrics["p50_ops_per_sec"] >= 0.0
        stage_samples += metrics["samples"]

    aggregate = result["aggregate"]
    assert aggregate["samples"] == stage_samples
    assert aggregate["p95_ops_per_sec"] >= aggregate["p50_ops_per_sec"] >= 0.0

    assert result["completed"]["stm_to_mtm"] == result["total_memories"]
    assert result["completed"]["mtm_to_ltm"] == result["total_memories"]


def test_high_concurrency_stress_reports_operations() -> None:
    result = run_high_concurrency_stress_scenario(
        concurrent_workers=4,
        operations_per_worker=6,
        preloaded_memories={
            "stm": 8,
            "mtm": 6,
            "ltm": 4,
        },
        content_length=64,
        random_seed=222,
    )

    assert result["workers"] == 4
    counts = result["operation_counts"]
    assert sum(counts.values()) == result["total_operations"]
    assert counts["ingest_stm"] > 0
    assert result["aggregate_throughput_ops_per_sec"] >= 0.0
    assert result["errors"] == []

    for op_name, metrics in result["latency_ms"].items():
        if counts[op_name] == 0:
            assert metrics["samples"] == 0
            continue

        assert metrics["samples"] == counts[op_name]
        assert metrics["max_ms"] >= metrics["min_ms"] >= 0.0
