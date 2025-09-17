"""Metacognition package exposing the primary monitor interface."""

from .monitor import MetacognitiveMonitor

# Backwards compatibility alias expected by API wiring
Metacognition = MetacognitiveMonitor

__all__ = ["MetacognitiveMonitor", "Metacognition"]
