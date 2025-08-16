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

    mgr = LLMIntegrationManager(cfg)
    try:
        resp = await mgr.query(
            prompt=body.prompt,
            provider=body.provider,
            model=body.model,
            max_tokens=body.max_tokens,
            temperature=body.temperature,
            memory_context=body.memory_context,
            health_aware=body.health_aware,
            goal_directed=body.goal_directed,
            additional_context=body.additional_context or {},
        )

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