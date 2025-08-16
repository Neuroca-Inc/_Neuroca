# Local LLM Quickstart (Ollama)

This guide shows how to run Neuroca with a local LLM backend via Ollama.

Prerequisites
- Ollama installed and running (https://ollama.com)
- A model pulled locally, e.g.:
  - macOS/Linux:
    - `ollama pull gemma3:4b`
  - Windows (WSL):
    - `ollama pull gemma3:4b`
- Python 3.10+ environment for Neuroca

Key Components
- Manager: ['python.class LLMIntegrationManager()'](_Neuroca/src/neuroca/integration/manager.py:39)
- Ollama Adapter: ['python.class OllamaAdapter()'](_Neuroca/src/neuroca/integration/adapters/ollama.py:45)
- Adapter Registry and Base: ['python.class AdapterRegistry()'](_Neuroca/src/neuroca/integration/adapters/base.py:452), ['python.class BaseAdapter()'](_Neuroca/src/neuroca/integration/adapters/base.py:235)
- Canonical LLM models: ['python.class LLMRequest()'](_Neuroca/src/neuroca/integration/models.py:115), ['python.class LLMResponse()'](_Neuroca/src/neuroca/integration/models.py:157), ['python.class ResponseType()'](_Neuroca/src/neuroca/integration/models.py:22)
- Prompt templates: ['python.class TemplateManager()'](_Neuroca/src/neuroca/integration/prompts/templates.py:113), default template file ['base_enhancement.j2'](_Neuroca/src/neuroca/integration/prompts/templates/base_enhancement.j2)

1) Configure Neuroca for Ollama
- Copy the provided example config and adjust as needed:
  - ['_Neuroca/config/local-llm.example.yaml'](_Neuroca/config/local-llm.example.yaml)
- Minimal config (defaults to Ollama if present):
  - default_provider: ollama
  - default_model: gemma3:4b
  - providers.ollama.base_url: http://localhost:11434

2) Minimal usage (Python)
Create a small script (e.g., scripts/run_local_llm.py):

```
import asyncio
from neuroca.integration.manager import LLMIntegrationManager

async def main():
    config = {
        "default_provider": "ollama",
        "default_model": "gemma3:4b",
        "providers": {
            "ollama": {
                "base_url": "http://localhost:11434",
                "default_model": "gemma3:4b",
                "request_timeout": 60,
                "max_retries": 2,
            }
        },
        "prompt_template_dirs": [],  # use base prompt without extra templating
        "store_interactions": False,
    }

    mgr = LLMIntegrationManager(config=config)
    try:
        resp = await mgr.query(
            prompt="Say hello from Neuroca via Ollama",
            provider="ollama",
            model="gemma3:4b",
            memory_context=False,
            health_aware=False,
            goal_directed=False,
            max_tokens=128,
            temperature=0.3,
        )
        print("Model:", resp.model)
        print("Provider:", resp.provider)
        print("Content:", resp.content)
        print("Metadata:", resp.metadata)
    finally:
        await mgr.close()

if __name__ == "__main__":
    asyncio.run(main())
```

Notes
- The manager will call the Ollama adapter’s execute(request) path:
  - ['python.method OllamaAdapter.execute()'](_Neuroca/src/neuroca/integration/adapters/ollama.py:167)
- If you provide prompt_template_dirs that contain Jinja or YAML templates, the manager will render a prompt via:
  - ['python.method TemplateManager.render_template()'](_Neuroca/src/neuroca/integration/prompts/templates.py:418)
- For a raw prompt (no templating), supply prompt_template_dirs: [] and the base prompt will be used directly.

3) Optional: Embeddings
You can generate embeddings directly via the adapter:
- ['python.method OllamaAdapter.generate_embedding()'](_Neuroca/src/neuroca/integration/adapters/ollama.py:369)
- Returns ['python.class LLMResponse()'](_Neuroca/src/neuroca/integration/models.py:157) with ['python.class ResponseType.EMBEDDING'](_Neuroca/src/neuroca/integration/models.py:22)

4) Tests (local smoke tests)
Two smoke tests were added to validate the local integration (with mocked HTTP client):
- Unit-ish adapter tests: ['_Neuroca/tests/unit/integration/test_ollama_adapter.py'](_Neuroca/tests/unit/integration/test_ollama_adapter.py)
- Manager end-to-end smoke test: ['_Neuroca/tests/integration/test_manager_ollama.py'](_Neuroca/tests/integration/test_manager_ollama.py)

Run only these tests to avoid unrelated suites:
- Linux/macOS:
  - PYTHONPATH=_Neuroca/src pytest -q _Neuroca/tests/unit/integration/test_ollama_adapter.py _Neuroca/tests/integration/test_manager_ollama.py
- Or install Neuroca in editable mode first:
  - pip install -e .
  - pytest -q _Neuroca/tests/unit/integration/test_ollama_adapter.py _Neuroca/tests/integration/test_manager_ollama.py

Troubleshooting
- “ModuleNotFoundError: neuroca”: set PYTHONPATH to point at _Neuroca/src or install with pip -e.
- “Ollama connection refused”: ensure the Ollama daemon is running and base_url is correct:
  - Default: http://localhost:11434
- Template errors: set prompt_template_dirs: [] to bypass templating and send base prompt only.

Status of the local LLM path (Ollama)
- Registry updated: adapters auto-register via ['python.method AdapterRegistry.register()'](_Neuroca/src/neuroca/integration/adapters/base.py:461)
- Manager prefers ollama as default if configured: ['python.method LLMIntegrationManager.__init__()'](_Neuroca/src/neuroca/integration/manager.py:47)
- Manager calls adapter.execute(request) (with fallback to generate() for legacy adapters): ['python.method LLMIntegrationManager.query()'](_Neuroca/src/neuroca/integration/manager.py:129)
- Ollama adapter conforms to BaseAdapter and supports AdapterConfig or dict config: ['python.class OllamaAdapter()'](_Neuroca/src/neuroca/integration/adapters/ollama.py:45)

Roadmap (next steps)
- Keep cloud adapters out of the critical path until refactor is complete (imports are guarded already).
- Optional: convert remaining adapters to the same execution interface and canonical models.
- Optional: add CLI command for local-LLM smoke run under ['_Neuroca/src/neuroca/cli/commands'](_Neuroca/src/neuroca/cli/commands)
