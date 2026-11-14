# CRACI Live Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the deployed front door publish live CRACI evidence for its own Render commit, with safe caching and artifact fallback.

**Architecture:** Extract the existing SBOM/network summarizers into `backend/app/craci_evidence.py`. Keep the CI script's transport and output flow, importing those summarizers. Add a synchronous, lazily-called live client with injected HTTP transport, a 10-second deadline, and success/failure TTL cache; have signing call it for the build document and link the same document from the JWK set.

**Tech Stack:** Python 3.13, FastAPI, `urllib.request`, pytest, mocked HTTP transports.

**Spec:** User task: live CRACI evidence for PR #116.

## Global Constraints

- Work only in `/Users/omar/Code/bpj-craci`; do not commit or push.
- CRACI tokens must never appear in responses, logs, or error text.
- Tests use mocked HTTP only; the real check is GitHub lookup for the current origin/main commit.
- Run backend tests with `PYTHONPATH=<worktree>/contracts:<worktree>/compiler:<worktree>/profile` and empty `GEMINI_API_KEY`.
- Keep `BUILD_PROVENANCE_PATH` as a fallback when live evidence is unavailable.

## Review Focus

- A CRACI 403 must become `reason: "craci_403"` without exposing the token.
- A GitHub response with no matching completed CI run must become `reason: "no_ci_run"`.
- Successful jobs must be hashed in GitHub job order, not lexical job-ID order.
- A cached failure must suppress repeat HTTP calls for five minutes, while cached success lasts one hour.
- The signing-key document and build endpoint must expose the same live/fallback object.

### Task 1: Extract summarizers and remove script diagnostics

**Files:**
- Create: `backend/app/craci_evidence.py`
- Modify: `scripts/craci_sbom.py`
- Test: `scripts/tests/test_craci_sbom.py`

**Interfaces:**
- Produces `summarize_sboms`, `summarize_network_trace`, and `exit_code` for both the script and live client.

- [ ] Write/import tests proving existing counts, dependencies, vulnerabilities, network destinations, and digest behavior.
- [ ] Run the script tests and verify the import/behavior failure before implementation.
- [ ] Move the summarizing functions, preserving output shape while hashing records in input/job order; import them from the script.
- [ ] Remove the CRACI active-job token check and fake-token reachability probe.
- [ ] Run script tests and the relevant backend package checks.

### Task 2: Implement live GitHub/CRACI fetch and cache

**Files:**
- Modify: `backend/app/craci_evidence.py`
- Create/modify: `backend/tests/test_craci_live.py`

**Interfaces:**
- `fetch_live_evidence(commit: str | None, token: str, repository: str = DEFAULT_REPOSITORY) -> dict`
- `clear_cache() -> None`

- [ ] Add mocked tests for success, 403, no CI run, no token, cache hit, and token redaction.
- [ ] Run those tests red and verify the missing live client behavior.
- [ ] Implement workflow-run selection, paginated CRACI job selection, evidence fetch, safe reason mapping, 10-second deadline, and 1-hour/5-minute cache.
- [ ] Run the focused tests green.

### Task 3: Wire the endpoint and signing keys

**Files:**
- Modify: `backend/app/signing.py`, `backend/app/main.py`, `backend/tests/test_craci_provenance.py`

**Interfaces:**
- The endpoint returns the live response fields and uses the artifact JSON only when live evidence is unavailable.

- [ ] Update endpoint tests for live success/failure and fallback, including key-document linkage.
- [ ] Run them red against the current artifact-only behavior.
- [ ] Wire `RENDER_GIT_COMMIT`, `CRACI_API_TOKEN`, and live evidence into `build_provenance`; leave startup non-blocking.
- [ ] Run focused and full backend tests.

### Task 4: Document and perform external verification

**Files:**
- Modify: `docs/CRACI.md`

- [ ] Document why live fetching exists, the 403 evidence, fields, and verifier SHA-256 recomputation.
- [ ] Run the unauthenticated GitHub lookup for the current `origin/main` commit and record the matching CI run and CRACI job IDs in the handoff.
- [ ] Run backend/package/script tests, `git diff --check`, and inspect the final diff; do not contact CRACI without the Render token.
