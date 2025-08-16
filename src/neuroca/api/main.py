"""Main API entry point for NeuroCognitive Architecture."""

import os

import uvicorn
from fastapi import FastAPI
from neuroca.api.routes.llm import router as llm_router

from neuroca.monitoring.logging import configure_logging, get_logger

# Initialize NeuroCa logging system
configure_logging(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="json" if os.environ.get("ENVIRONMENT", "development") == "production" else "detailed",
    output="file" if os.environ.get("ENVIRONMENT", "development") == "production" else "console"
)
logger = get_logger(__name__)

# Create FastAPI app
app = FastAPI(
    title="NeuroCognitive Architecture API",
    description="API for the NeuroCognitive Architecture (NCA)",
    version="0.1.0",
)

# Expose a persistent LLM JSON endpoint at /api/llm/query
app.include_router(llm_router, prefix="/api")


@app.get("/")
async def root():
    """Root endpoint."""
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
