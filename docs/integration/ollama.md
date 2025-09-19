# Ollama Integration

Ollama function-calling is not supported in 1.0.0‑rc1. The adapter raises a clear NotImplemented error when function-calling is requested. This is currently in development and should be supported shortly.

## Usage

- Text/chat usage works via the adapter.
- Avoid function-calling modes; wrap tool calls in your agent loop instead.

## Rationale

- Stable, provider-agnostic behavior across agents.
- Keeps default surface small while we validate demand and semantics.
