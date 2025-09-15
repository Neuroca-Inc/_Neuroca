"""Main API entry point for NeuroCognitive Architecture."""

import os

import uvicorn
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from neuroca.api.routes.llm import router as llm_router

from neuroca.monitoring.logging import configure_logging, get_logger

# Initialize NeuroCa logging system
configure_logging(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="json" if os.environ.get("ENVIRONMENT", "development") == "production" else "detailed",
    # Pass output as a string to match configure_logging's expected type
    output="file" if os.environ.get("ENVIRONMENT", "development") == "production" else "console",
)
logger = get_logger(__name__)

# Create FastAPI app
app = FastAPI(
    title="NeuroCognitive Architecture API",
    description="API for the NeuroCognitive Architecture (NCA)",
    version="0.1.0",
)

# Mount static frontend UI (served at /ui) if present
UI_AVAILABLE = False
try:
    # main.py is at: _Neuroca/src/neuroca/api/main.py
    # parents[1] => _Neuroca/src/neuroca; mount frontend at _Neuroca/src/neuroca/frontend
    FE_DIR = Path(__file__).resolve().parents[1] / "frontend"
    if FE_DIR.exists():
        app.mount("/ui", StaticFiles(directory=str(FE_DIR), html=True), name="ui")
        UI_AVAILABLE = True
except Exception:
    # Non-fatal; API still functions without UI mount
    UI_AVAILABLE = False

# Expose a persistent LLM JSON endpoint at /api/llm/query
app.include_router(llm_router, prefix="/api")


@app.get("/")
async def root():
    """Root endpoint."""
    if UI_AVAILABLE:
        return RedirectResponse(url="/ui")
    return {"message": "Welcome to the NeuroCognitive Architecture API"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


def start():
    """Start the API server."""
    logger.info("Starting NeuroCognitive Architecture API")
    uvicorn.run(
        "neuroca.api.main:app",
        host=os.environ.get("API_HOST", "127.0.0.1"),  # Default to localhost
        port=int(os.environ.get("API_PORT", 8000)),
        reload=os.environ.get("API_RELOAD", "false").lower() == "true",
    )


if __name__ == "__main__":
    start()
