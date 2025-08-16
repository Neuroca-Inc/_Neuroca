"""
Neuroca LLM Benchmarks (modular package)

Subpackages/modules:
- util.py: shared helpers (normalization, MCQ parsing, manager config, unified call)
- datasets.py: small embedded datasets for hallucination/exam/reward-hacking
- latency.py: latency benchmark
- memory_growth.py: tracemalloc/optional RSS trend benchmark
- resilience.py: load/resilience benchmark
- hallucination.py: factual QA with normalization
- exam.py: MCQ accuracy with strict parsing
- reward_hacking.py: adversarial prompts to detect reward hacking
- cli.py: CLI entrypoint and orchestration
"""

__version__ = "0.1.0"

__all__ = [
    "__version__",
]