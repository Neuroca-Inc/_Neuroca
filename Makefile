# Neuroca Dev Makefile (repo root)
# Usage:
#   make venv
#   make install
#   make dev-api
#   make open-ui
#   make clean

.PHONY: help venv pip-upgrade install dev-api dev-api-uvicorn open-ui release-checks clean

VENV := venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

help:
	@echo "Targets:"
	@echo "  make venv        - create virtualenv at ./venv"
	@echo "  make install     - pip install -e ./_Neuroca and runtime deps"
	@echo "  make dev-api     - run API server at http://127.0.0.1:8000 (serves /ui)"
	@echo "  make open-ui     - open http://127.0.0.1:8000/ui"
	@echo "  make release-checks - run pytest, scoped Ruff lint, and mypy"
	@echo "  make clean       - remove venv"

venv:
	python3 -m venv $(VENV)

pip-upgrade: | venv
	$(PIP) install --upgrade pip

install: | venv pip-upgrade
	# Install the Neuroca package from the project subdir (_Neuroca)
	$(PIP) install -e ./_Neuroca
	# Ensure app runner is available
	$(PIP) install "uvicorn[standard]"

# Preferred: use installed entrypoint neuroca-api; fall back to uvicorn module run if needed
dev-api: | install
	@echo "Starting Neuroca API on http://127.0.0.1:8000 ..."
	@($(VENV)/bin/neuroca-api) || ($(PY) -m uvicorn neuroca.api.main:app --host 127.0.0.1 --port 8000 --reload)

# Explicit uvicorn runner (alternative)
dev-api-uvicorn: | install
	$(PY) -m uvicorn neuroca.api.main:app --host 127.0.0.1 --port 8000 --reload

open-ui:
	@xdg-open http://127.0.0.1:8000/ui 2>/dev/null || echo "Open http://127.0.0.1:8000/ui"

release-checks:
	pytest -q
	ruff check \
		src/neuroca/core/enums.py \
		src/neuroca/core/cognitive_control/_async_utils.py \
		src/neuroca/core/cognitive_control/decision_maker.py \
		src/neuroca/core/cognitive_control/planner.py \
		src/neuroca/core/cognitive_control/metacognition.py \
		src/neuroca/memory/manager/memory_manager.py \
		src/neuroca/memory/service.py
	mypy --hide-error-context --no-error-summary

clean:
	rm -rf $(VENV)
