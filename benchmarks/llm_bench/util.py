from __future__ import annotations

import re
import unicodedata
from typing import Optional, Dict, Any

from neuroca.integration.manager import LLMIntegrationManager
from neuroca.integration.models import LLMResponse


# Unicode subscript numerals to ASCII mapping (e.g., H₂O -> H2O)
_SUBSCRIPT_MAP = str.maketrans({
    "₀": "0", "₁": "1", "₂": "2", "₃": "3", "₄": "4",
    "₅": "5", "₆": "6", "₇": "7", "₈": "8", "₉": "9",
    "₊": "+", "₋": "-", "₌": "=", "₍": "(", "₎": ")",
})


def canonicalize_text(text: str, *, lowercase: bool = True, strip_markdown: bool = True) -> str:
    """
    Normalize model output for robust comparisons in benchmarks:
    - Unicode NFKD normalization
    - Replace subscript numerals with ASCII
    - Optionally remove simple Markdown emphasis (**bold**, *italic*)
    - Collapse whitespace
    - Optional lowercasing
    """
    if text is None:
        return ""

    # NFKD decomposition
    norm = unicodedata.normalize("NFKD", text)

    # Replace subscript chars (common in chemistry like H₂O)
    norm = norm.translate(_SUBSCRIPT_MAP)

    # Strip simple markdown emphasis
    if strip_markdown:
        # remove **text** and *text* markers (leave inner text)
        norm = re.sub(r"\*\*(.*?)\*\*", r"\1", norm)
        norm = re.sub(r"\*(.*?)\*", r"\1", norm)
        # remove backticks
        norm = norm.replace("`", "")

    # Collapse whitespace
    norm = re.sub(r"\s+", " ", norm).strip()

    if lowercase:
        norm = norm.lower()

    return norm


_MCQ_RE = re.compile(r"^\s*([A-D])\b", re.IGNORECASE)


def extract_mcq_letter(answer: str) -> str:
    """
    Extract a single MCQ letter (A-D) from model output.
    Strategy:
    - Take the first line
    - Match a leading letter [A-D] if present
    - Fallback: first occurrence of A/B/C/D in the string
    - Return uppercase letter, or empty string if none
    """
    if not answer:
        return ""
    first_line = answer.splitlines()[0]
    m = _MCQ_RE.match(first_line)
    if m:
        return m.group(1).upper()
    for ch in first_line.upper():
        if ch in {"A", "B", "C", "D"}:
            return ch
    return ""


async def call_llm(
    mgr: LLMIntegrationManager,
    prompt: str,
    provider: str,
    model: str,
    max_tokens: Optional[int] = 128,
    temperature: float = 0.2,
    **kwargs,
) -> LLMResponse:
    """
    Unified LLM call used across suites. Disables memory/health/goal by default
    for clean, reproducible benchmarking.
    """
    return await mgr.query(
        prompt=prompt,
        provider=provider,
        model=model,
        memory_context=False,
        health_aware=False,
        goal_directed=False,
        max_tokens=max_tokens,
        temperature=temperature,
        **kwargs,
    )


def build_manager_config(provider: str, model: str, *, template_dirs: Optional[list[str]] = None) -> Dict[str, Any]:
    """
    Construct a minimal LLMIntegrationManager configuration for benchmarks.
    By default, disables template directories to avoid template warnings and
    ensure the base prompt is used.
    """
    cfg = {
        "default_provider": provider,
        "default_model": model,
        "providers": {
            provider: {
                # These fields are harmless for non-Ollama providers; for Ollama they are used.
                "base_url": "http://127.0.0.1:11434",
                "default_model": model,
                "request_timeout": 60,
                "max_retries": 2,
            }
        },
        "store_interactions": False,
    }
    if template_dirs is None:
        # No template dirs: manager will fallback to base prompt (no warning)
        cfg["prompt_template_dirs"] = []
    else:
        cfg["prompt_template_dirs"] = template_dirs
    return cfg