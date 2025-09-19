# Release Process

This document describes how to cut a Neuroca release.

## Versioning

- RCs: use semantic version with `-rcN` suffix (e.g., `1.0.0-rc1`).
- GA: drop the suffix (e.g., `1.0.0`).

## Steps (RC → GA)

1. Ensure CI green on `main` (tests, lint, Trivy scan).
2. Update `pyproject.toml` and `src/neuroca/config/settings.py` version.
3. Update `docs/RELEASE_NOTES.md` with highlights and any breaking changes.
4. Tag and publish a GitHub release:
   - Tag format: `v1.0.0-rc1` (RC) or `v1.0.0` (GA)
   - The `publish.yml` workflow will publish to TestPyPI (RC) and PyPI (GA) when the release is published.
5. Build and test the Docker image locally:

   ```bash
   docker build -t neuroca:1.0.0 .
   docker run --rm -p 8000:8000 neuroca:1.0.0
   curl -sf http://localhost:8000/health
   ```

6. (Optional) Push to your container registry (requires configured credentials):

   ```bash
   docker tag neuroca:1.0.0 ghcr.io/<org>/neuroca:1.0.0
   docker push ghcr.io/<org>/neuroca:1.0.0
   ```

## RC Soak Test

- Run the soak per `docs/operations/runbooks/soak-test.md` for 3–5 days.
- If stable, promote `1.0.0-rcX` → `1.0.0` by bumping versions and publishing a GA release.

## Post-Release

- Verify docs publishing (`mkdocs-deploy.yml`).
- Announce and provide upgrade notes.
