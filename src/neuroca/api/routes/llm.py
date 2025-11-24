"""
LLM Application Endpoints (backed by local Ollama by default)

This router exposes a simple JSON API that wraps the in-repo LLMIntegrationManager,
so users can interact with models via a persistent application (no CLI required).

Key endpoints:
- POST /api/llm/query: single-turn prompt → response JSON

Defaults target a local Ollama daemon (http://127.0.0.1:11434) with model "gemma3:4b".
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

# Import the canonical manager/types from the integration layer
from neuroca.integration.manager import LLMIntegrationManager

# Lightweight in-process conversational memory (per session_id)
from collections import deque
from typing import Deque, Dict

SESSIONS: Dict[str, Deque[str]] = {}

# Optional managers (created only when the user enables related features)
try:
    from neuroca.core.cognitive_control.goal_manager import GoalManager  # type: ignore
except Exception:
    GoalManager = None  # type: ignore
try:
    from neuroca.core.health.dynamics import HealthDynamicsManager  # type: ignore
except Exception:
    HealthDynamicsManager = None  # type: ignore
try:
    # Pragmatic factory hook; adjust to your actual memory system entrypoint
    from neuroca.memory.factory import create_memory_system  # type: ignore
except Exception:
    create_memory_system = None  # type: ignore

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/llm",
    tags=["LLM"],
    responses={401: {"description": "Unauthorized"}, 500: {"description": "Internal Server Error"}},
)


# ---------- Request/Response Schemas ----------

class LLMQueryRequest(BaseModel):
    prompt: str = Field(..., description="The prompt to send to the model")
    provider: str = Field("ollama", description="Provider name (default: ollama)")
    model: str = Field("gemma3:4b", description="Model name (default: gemma3:4b)")

    # Generation params
    max_tokens: int = Field(128, ge=1, le=4096, description="Maximum tokens to generate")
    temperature: float = Field(0.2, ge=0.0, le=2.0, description="Sampling temperature")

    # Context knobs (disabled by default for simple local runs)
    memory_context: bool = Field(False, description="Enable memory-enhanced context")
    health_aware: bool = Field(False, description="Enable health-aware context")
    goal_directed: bool = Field(False, description="Enable goal-directed context")

    # Optional arbitrary metadata/context to pass through
    additional_context: Optional[dict[str, Any]] = Field(
        None, description="Additional context to pass to the manager"
    )
    # Output shaping / verbosity controls
    style: Optional[str] = Field(
        default="detailed",
        description="Response style hint (e.g., 'concise', 'detailed', 'step_by_step')"
    )
    verbosity: Optional[int] = Field(
        default=3, ge=0, le=10,
        description="Verbosity preference (0-10). Higher tends to produce longer answers"
    )


class Usage(BaseModel):
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None


class LLMQueryResponse(BaseModel):
    content: str
    provider: str
    model: str
    usage: Optional[Usage] = None
    elapsed_time: Optional[float] = None
    metadata: Optional[dict[str, Any]] = None


# ---------- Helpers ----------

def _default_config(provider: str, model: str) -> dict[str, Any]:
    """
    Build a minimal in-process config that targets local Ollama by default.
    This avoids requiring any external YAML for a basic single-shot request.
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
        "prompt_template_dirs": [],
        "store_interactions": False,
    }


def _compose_prompt(
    raw_prompt: str,
    *,
    style: str = "detailed",
    verbosity: int = 3,
    system_directive: str = "",
    history: Optional[Deque[str]] = None,
) -> str:
    """
    Build an enriched prompt so UI controls actually affect generation
    even when the template system is not active.

    - style: 'concise' | 'detailed' | 'step_by_step'
    - verbosity: 0..10 (soft hint for length/coverage)
    - system_directive: freeform system instruction
    - history: prior turns stored for the given session_id
    """
    style_map = {
        "concise": "Respond succinctly with minimal words while preserving key facts.",
        "detailed": "Respond comprehensively with clear structure, examples, and explanations.",
        "step_by_step": "Reason step-by-step. Show intermediate steps, assumptions, constraints, and examples.",
    }
    style_text = style_map.get(style.lower(), style_map["detailed"])
    vb = max(0, min(10, int(verbosity)))
    verbosity_text = f"Verbosity preference: {vb}/10. Higher verbosity means more detail and thorough coverage."

    lines: list[str] = []
    lines.append("System: You are Neuroca's local assistant operating over a local LLM. Follow all instructions faithfully.")
    if system_directive:
        lines.append(f"System Directive: {system_directive}")
    lines.append(f"Style: {style_text}")
    lines.append(verbosity_text)

    if history and len(history) > 0:
        # Include only the latest few turns to bound context
        recent = list(history)[-6:]
        lines.append("\nPrevious context:")
        for i, h in enumerate(recent, 1):
            lines.append(f"{i:02d}. {h}")

    lines.append("\nUser:")
    lines.append(raw_prompt)
    return "\n".join(lines)


# ---------- Routes ----------

@router.post(
    "/query",
    summary="Query the LLM",
    response_model=LLMQueryResponse,
)
async def query_llm(body: LLMQueryRequest) -> LLMQueryResponse:
    """
    Execute a single prompt through the LLMIntegrationManager.

    Example:
      POST /api/llm/query
      {
        "prompt": "Say hello concisely.",
        "provider": "ollama",
        "model": "gemma3:4b",
        "max_tokens": 64,
        "temperature": 0.2
      }
    """
    cfg = _default_config(body.provider, body.model)

    # Conditionally construct optional managers so toggles actually take effect
    memory_manager = None
    health_manager = None
    goal_manager = None

    if body.memory_context and create_memory_system:
        try:
            # Use a lightweight default memory system suitable for local runs
            memory_manager = create_memory_system()
            await memory_manager.initialize()
        except Exception:
            logger.exception("Unable to initialize memory manager for LLM route")
            memory_manager = None  # non-fatal

    if body.health_aware and HealthDynamicsManager:
        try:
            _hm = HealthDynamicsManager()
            # Guard: only pass health manager if it exposes the interface the manager expects
            if hasattr(_hm, "get_system_health"):
                health_manager = _hm
            else:
                health_manager = None  # avoid AttributeError in integration manager
        except Exception:
            health_manager = None  # non-fatal

    if body.goal_directed and GoalManager:
        try:
            goal_manager = GoalManager(
                health_manager=health_manager,
                memory_manager=memory_manager,
            )
        except Exception:
            goal_manager = None  # non-fatal

    # Enrich additional_context with style/verbosity hints so templates (or adapters) can use them
    extra_ctx: dict[str, Any] = {}
    if body.additional_context:
        extra_ctx.update(body.additional_context)
    extra_ctx.setdefault("response_style", body.style or "detailed")
    extra_ctx.setdefault("verbosity", body.verbosity if body.verbosity is not None else 3)

    # Session parameters for lightweight conversational memory (in-process)
    session_id = str(extra_ctx.get("session_id", "local-session"))
    system_directive = str(extra_ctx.get("system_directive", ""))
    hist = SESSIONS.setdefault(session_id, deque(maxlen=20))

    # Compose enriched prompt so style/verbosity/history actually affect outputs
    enriched_prompt = _compose_prompt(
        body.prompt,
        style=(body.style or "detailed"),
        verbosity=int(body.verbosity if body.verbosity is not None else 3),
        system_directive=system_directive,
        history=hist,
    )

    # (deduplicated) session setup and prompt composition already performed above

    mgr = LLMIntegrationManager(
        config=cfg,
        memory_manager=memory_manager,
        health_manager=health_manager,
        goal_manager=goal_manager,
    )
    try:
        # If the template system is active, style/verbosity will be consumed there.
        # Otherwise they remain as hints for downstream adapters or post-processing.
        resp = await mgr.query(
            prompt=enriched_prompt,
            provider=body.provider,
            model=body.model,
            max_tokens=body.max_tokens,
            temperature=body.temperature,
            memory_context=bool(memory_manager) and body.memory_context,
            health_aware=bool(health_manager) and body.health_aware,
            goal_directed=bool(goal_manager) and body.goal_directed,
            additional_context=extra_ctx,
        )

        # Update ephemeral session memory with this turn
        try:
            hist.append(f"User: {body.prompt}")
            hist.append(f"Assistant: {(resp.content or '')[:2000]}")
        except Exception:
            pass

        # Shape response into a stable JSON envelope
        usage = None
        try:
            if getattr(resp, "usage", None):
                usage = Usage(
                    prompt_tokens=getattr(resp.usage, "prompt_tokens", None),
                    completion_tokens=getattr(resp.usage, "completion_tokens", None),
                    total_tokens=getattr(resp.usage, "total_tokens", None),
                )
        except Exception:
            # Non-fatal; usage is optional
            pass

        return LLMQueryResponse(
            content=(resp.content or ""),
            provider=getattr(resp, "provider", body.provider),
            model=getattr(resp, "model", body.model),
            usage=usage,
            elapsed_time=getattr(resp, "elapsed_time", None),
            metadata=getattr(resp, "metadata", None),
        )
    except Exception as e:
        logger.exception("LLM query failed")
        # For local Ollama not running: return 502 rather than 500 to hint upstream failure
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM query failed: {str(e)}",
        ) from e
    finally:
        try:
            await mgr.close()
        except Exception:
            pass
        if memory_manager and hasattr(memory_manager, "shutdown"):
            try:
                await memory_manager.shutdown()
            except Exception:
                logger.debug("Memory manager shutdown failed", exc_info=True)

# --- Streaming SSE endpoint (Ollama-first, with memory visibility) ---

@router.get(
    "/stream",
    summary="Stream LLM output via SSE",
)
async def stream_llm(
    prompt: str,
    provider: str = "ollama",
    model: str = "gemma3:4b",
    max_tokens: int = 128,
    temperature: float = 0.2,
    memory_context: bool = False,
    health_aware: bool = False,
    goal_directed: bool = False,
    style: str = "detailed",
    verbosity: int = 3,
    session_id: Optional[str] = None,
    system_directive: str = "",
):
    """
    Server-Sent Events (SSE) streaming endpoint.

    Behavior:
    - If provider is 'ollama' and local daemon is reachable, stream tokens directly from Ollama.
    - Otherwise, fall back to a single-shot manager.query and pseudo-stream the final content.
    - Emits a 'meta' event first with memory hits so you can verify memory integration live.

    SSE event format (text/event-stream):
        data: {"type":"meta","memory_hits":...,"memories":[...],...}

        data: {"type":"token","content":"..."}

        data: {"type":"end","elapsed":...}
    """
    # Local imports to avoid changing module header imports
    from fastapi.responses import StreamingResponse
    import aiohttp
    import json
    import time

    # Build a minimal config just like the JSON route
    cfg = _default_config(provider, model)

    # Optional managers
    _memory_manager = None
    _health_manager = None
    _goal_manager = None

    if memory_context and create_memory_system:
        try:
            _memory_manager = create_memory_system()
            await _memory_manager.initialize()
        except Exception:
            logger.exception("Unable to initialize memory manager for streaming LLM route")
            _memory_manager = None  # non-fatal

    if health_aware and HealthDynamicsManager:
        try:
            _hm = HealthDynamicsManager()
            if hasattr(_hm, "get_system_health"):
                _health_manager = _hm
        except Exception:
            _health_manager = None  # non-fatal

    if goal_directed and GoalManager:
        try:
            _goal_manager = GoalManager(
                health_manager=_health_manager,
                memory_manager=_memory_manager,
            )
        except Exception:
            _goal_manager = None  # non-fatal

    # Additional context and lightweight session memory
    extra_ctx: dict[str, Any] = {}
    extra_ctx.setdefault("response_style", style or "detailed")
    extra_ctx.setdefault("verbosity", verbosity if verbosity is not None else 3)
    if session_id:
        extra_ctx["session_id"] = session_id
    if system_directive:
        extra_ctx["system_directive"] = system_directive

    sid = str(extra_ctx.get("session_id", "local-session"))
    hist = SESSIONS.setdefault(sid, deque(maxlen=20))

    enriched_prompt = _compose_prompt(
        prompt,
        style=(style or "detailed"),
        verbosity=int(verbosity if verbosity is not None else 3),
        system_directive=(system_directive or ""),
        history=hist,
    )

    # Create a manager instance for memory retrieval and standardization
    mgr = LLMIntegrationManager(
        config=cfg,
        memory_manager=_memory_manager,
        health_manager=_health_manager,
        goal_manager=_goal_manager,
    )

    def _sse_line(obj: dict) -> bytes:
        return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n".encode("utf-8")

    async def _gen():
        t0 = time.perf_counter()
        full_text: list[str] = []
        try:
            # Emit metadata first with memory hits so UI can display verification
            mem_hits = 0
            mem_previews: list[str] = []
            if memory_context and mgr.memory_manager:
                try:
                    # Reuse manager's retrieval method for consistent behavior across tiers
                    mems = await mgr._retrieve_relevant_memories(prompt)  # type: ignore[attr-defined]
                    mem_hits = len(mems or [])
                    if mem_hits:
                        for m in (mems or [])[:3]:
                            mem_previews.append(str(m.get("content", ""))[:200])
                except Exception:
                    pass

            yield _sse_line({
                "type": "meta",
                "provider": provider,
                "model": model,
                "memory_hits": mem_hits,
                "memories": mem_previews,
                "session_id": sid,
            })

            # Streaming path for Ollama if available; otherwise pseudo-stream
            if provider.lower() == "ollama":
                base_url = (
                    cfg.get("providers", {})
                      .get(provider, {})
                      .get("base_url", "http://127.0.0.1:11434")
                )
                timeout_sec = (
                    cfg.get("providers", {})
                      .get(provider, {})
                      .get("request_timeout", 60)
                )

                # Ollama generate payload with streaming
                payload = {
                    "model": model,
                    "prompt": enriched_prompt,
                    "stream": True,
                    "options": {
                        "temperature": float(temperature),
                        # Ollama uses num_predict as max tokens
                        "num_predict": int(max_tokens),
                    },
                }

                try:
                    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout_sec)) as session:
                        async with session.post(f"{base_url}/api/generate", json=payload) as resp:
                            resp.raise_for_status()
                            # Read newline-delimited JSON records
                            async for raw in resp.content:
                                if not raw:
                                    continue
                                try:
                                    for line in raw.decode("utf-8", "ignore").splitlines():
                                        s = line.strip()
                                        if not s:
                                            continue
                                        d = json.loads(s)
                                        tok = d.get("response")
                                        if tok:
                                            full_text.append(tok)
                                            yield _sse_line({"type": "token", "content": tok})
                                        if d.get("done"):
                                            # End of stream
                                            elapsed = time.perf_counter() - t0
                                            yield _sse_line({"type": "end", "elapsed": elapsed})
                                            # Update ephemeral session memory
                                            try:
                                                hist.append(f"User: {prompt}")
                                                hist.append(f"Assistant: {(''.join(full_text))[:2000]}")
                                            except Exception:
                                                pass
                                            return
                                except Exception:
                                    # Malformed line; continue
                                    continue
                except Exception:
                    # On streaming failure, fall back to a single result via manager
                    logger.exception("Streaming failure encountered; falling back to single-shot query")
                    pass  # Fall through to single-shot path below

            # Fallback: single-shot via manager, pseudo-stream once
            try:
                resp = await mgr.query(
                    prompt=enriched_prompt,
                    provider=provider,
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    memory_context=bool(_memory_manager) and memory_context,
                    health_aware=bool(_health_manager) and health_aware,
                    goal_directed=bool(_goal_manager) and goal_directed,
                    additional_context=extra_ctx,
                )
                text = resp.content or ""
                if text:
                    full_text.append(text)
                    yield _sse_line({"type": "token", "content": text})
                elapsed = time.perf_counter() - t0
                yield _sse_line({"type": "end", "elapsed": elapsed})
                # Update ephemeral session memory
                try:
                    hist.append(f"User: {prompt}")
                    hist.append(f"Assistant: {(text)[:2000]}")
                except Exception:
                    pass
                return
            except Exception as e:
                # Emit an error then end
                yield _sse_line({"type": "error", "message": str(e)})
                elapsed = time.perf_counter() - t0
                yield _sse_line({"type": "end", "elapsed": elapsed})
                return
        finally:
            try:
                await mgr.close()
            except Exception:
                pass
            if _memory_manager and hasattr(_memory_manager, "shutdown"):
                try:
                    await _memory_manager.shutdown()
                except Exception:
                    logger.debug("Streaming memory manager shutdown failed", exc_info=True)

    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",  # Disable nginx buffering if present
    }
    return StreamingResponse(_gen(), media_type="text/event-stream", headers=headers)