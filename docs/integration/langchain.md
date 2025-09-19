# LangChain Integration (Optional)

LangChain support is optional in Neuroca and is not installed by default for the 1.0.0‑rc1 release. This keeps the core secure and lightweight.

## Install

```bash
pip install '.[integrations]'
```

## Scope for 1.0

- Combined memory type: gated for 1.0 — not implemented by default.
- Existing adapters remain, but the project does not ship a composite memory that merges multiple tiers for LangChain. If needed, implement a thin aggregator in your app using MemoryManager’s query APIs.

## Rationale

- Minimize default surface area and dependency risks.
- Many users embed Neuroca behind their own agent loop without LangChain.

## Next steps

- If you need a combined memory for LangChain, open an issue with requirements. We can provide a reference aggregator targeting your use case.
