#!/usr/bin/env python3
"""
Local Ollama Runner (no PYTHONPATH required)

Usage (from repository root):

1) Single prompt (default provider=ollama, model=gemma3:4b)
   python _Neuroca/run_local_ollama.py prompt "Say hello concisely."

   Options:
     --model llama3
     --max-tokens 64
     --temperature 0.2

2) Benchmark suite (latency, memory, resilience, hallucination, exam, reward_hacking)
   python _Neuroca/run_local_ollama.py bench --model gemma3:4b --suite all --runs 10 --concurrency 2 --pretty --explain

Prerequisites:
- Ollama daemon running: `ollama serve`
- Model pulled: `ollama pull gemma3:4b` or `ollama pull llama3`
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


# --- Bootstrap imports so this works from repo root without env vars ---

THIS_DIR = Path(__file__).resolve().parent           # .../_Neuroca
SRC_DIR = THIS_DIR / "src"                           # .../_Neuroca/src

# Add _Neuroca for importing "benchmarks.llm_benchmarks"
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))
# Add _Neuroca/src for importing neuroca.*
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Now safe to import repo modules
from neuroca.integration.manager import LLMIntegrationManager  # noqa: E402
from neuroca.integration.models import LLMResponse             # noqa: E402

try:
    # Import the benchmark orchestrator
    import benchmarks.llm_benchmarks as bench  # noqa: E402
except Exception:  # If benchmarks module isn't importable for any reason
    bench = None

# Quiet overly verbose logging during CLI runs
logging.getLogger("neuroca.integration").setLevel(logging.WARNING)
logging.getLogger("neuroca.integration.prompts").setLevel(logging.WARNING)


# --- CLI actions ---

def _default_config(provider: str, model: str) -> Dict[str, Any]:
    """
    Build a minimal Manager config for local Ollama.
    """
    return {
        "default_provider": provider,
        "default_model": model,
        "providers": {
            provider: {
                "base_url": "http://127.0.0.1:11434",
                "default_model": model,
                "request_timeout": 60,
                "max_retries": 2,
            }
        },
        # No external template dirs required; manager registers a default enhancement template
        "prompt_template_dirs": [],
        "store_interactions": False,
    }


async def do_prompt(
    text: str,
    *,
    provider: str = "ollama",
    model: str = "gemma3:4b",
    max_tokens: int = 64,
    temperature: float = 0.2,
) -> None:
    """
    Execute a single prompt via LLMIntegrationManager and print the response text.
    """
    cfg = _default_config(provider, model)
    mgr = LLMIntegrationManager(cfg)
    try:
        resp: LLMResponse = await mgr.query(
            prompt=text,
            provider=provider,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            memory_context=False,
            health_aware=False,
            goal_directed=False,
        )
        print(resp.content or "")
    finally:
        await mgr.close()


async def do_bench(
    *,
    provider: str = "ollama",
    model: str = "gemma3:4b",
    suite: str = "all",
    runs: int = 20,
    concurrency: int = 2,
    pretty: bool = False,
    explain: bool = False,
) -> None:
    """
    Run the benchmark suite using the same in-repo orchestrator (no PYTHONPATH needed).
    """
    if bench is None:
        raise RuntimeError("Benchmarks module not available.")

    # Translate suite string to list
    suites: List[str] = [s.strip().lower() for s in suite.split(",") if s.strip()]
    if "all" in suites:
        suites = ["latency", "memory", "resilience", "hallucination", "exam", "reward_hacking"]

    results = await bench.run_suite(
        provider=provider,
        model=model,
        suite=suites,
        runs=runs,
        concurrency=concurrency,
        pretty=pretty,
    )

    # Print summary in addition to JSON if requested
    if explain and isinstance(results, dict):
        try:
            bench._print_summary(results)  # type: ignore[attr-defined]
        except Exception:
            # Minimal fallback summary
            print("\n=== Benchmark Summary (minimal) ===")
            if "resilience" in results:
                res = results["resilience"]
                print(f"[resilience] success: {res.get('success_rate', 0)}%  errors: {res.get('errors', 0)}")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Local Ollama runner (prompt and benchmark)")
    sub = p.add_subparsers(dest="cmd", required=True)

    # prompt subcommand
    sp = sub.add_parser("prompt", help="Run a single prompt through the local Ollama manager")
    sp.add_argument("text", type=str, help="Prompt text to send")
    sp.add_argument("--provider", type=str, default="ollama", help="Provider name (default: ollama)")
    sp.add_argument("--model", type=str, default="gemma3:4b", help="Model name (default: gemma3:4b)")
    sp.add_argument("--max-tokens", type=int, default=64, help="Max tokens (default: 64)")
    sp.add_argument("--temperature", type=float, default=0.2, help="Temperature (default: 0.2)")

    # bench subcommand
    sb = sub.add_parser("bench", help="Run the local benchmark suite")
    sb.add_argument("--provider", type=str, default="ollama", help="Provider name (default: ollama)")
    sb.add_argument("--model", type=str, default="gemma3:4b", help="Model name (default: gemma3:4b)")
    sb.add_argument(
        "--suite",
        type=str,
        default="all",
        help="Comma-separated: latency,memory,resilience,hallucination,exam,reward_hacking,all (default: all)",
    )
    sb.add_argument("--runs", type=int, default=20, help="Runs for applicable suites (default: 20)")
    sb.add_argument("--concurrency", type=int, default=2, help="Concurrency for applicable suites (default: 2)")
    sb.add_argument("--pretty", action="store_true", help="Pretty-print JSON results")
    sb.add_argument("--explain", action="store_true", help="Print a concise human-readable summary")

    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.cmd == "prompt":
        asyncio.run(
            do_prompt(
                args.text,
                provider=args.provider,
                model=args.model,
                max_tokens=args.max_tokens,
                temperature=args.temperature,
            )
        )
        return 0

    if args.cmd == "bench":
        if bench is None:
            print("Benchmarks module not available; cannot run 'bench'.")
            return 2
        asyncio.run(
            do_bench(
                provider=args.provider,
                model=args.model,
                suite=args.suite,
                runs=args.runs,
                concurrency=args.concurrency,
                pretty=args.pretty,
                explain=args.explain,
            )
        )
        return 0

    print("Unknown command.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())