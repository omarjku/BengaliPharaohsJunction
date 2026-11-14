Created [`.github/workflows/ci.yml`](/Users/omar/Code/bpj-ci/.github/workflows/ci.yml).

It includes:

- Push-to-`main` and pull request triggers
- Backend, package-matrix, and frontend jobs
- Python 3.13, Node 22, pip/npm caching
- Read-only permissions and cancellable concurrency
- One-line runner switch from `ubuntu-latest` to `craci`
- No secrets

Verification:

- Frontend `npm ci`, lint, and build passed.
- YAML and workflow checks passed.
- Python tests were attempted in a temporary venv but dependency installation was blocked by unavailable PyPI DNS; no application code was changed.