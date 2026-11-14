# Signed Provenance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make every signed order response identify the Render commit, CI run, and SBOM digest of the build that issued it.

**Architecture:** Derive a compact provenance object from the cached live CRACI evidence path without waiting for network refreshes. Put that exact object in the response and signed statement, derive the signing `kid` from the public key plus build commit while accepting statement-bound historical kids, and keep the existing full evidence document for public inspection.

**Tech Stack:** FastAPI/Python, Ed25519 via `cryptography`, pytest, React/TypeScript, Markdown.

**Spec:** User task “Best Use of CRACI, provenance” in the current conversation.

## Global Constraints

- Work only inside `/Users/omar/Code/bpj-sign`; do not commit or push.
- Signed provenance calls `craci_evidence.fetch_live_evidence(..., wait=False)` and never falls back to `BUILD_PROVENANCE_PATH`.
- Unavailable evidence still signs `commit`, `ci_run: null`, `sbom_sha256: null`, `evidence_status: "unavailable"`, and the fixed evidence URL.
- `/api/verify` must verify the build-covered signature, and old statements remain verifiable when the public key is unchanged.
- Full backend suite, frontend build if touched, and `git diff --check` are required gates.

## Review Focus

- A cache miss must return immediately and sign unavailable evidence; test the exact non-waiting call and no file fallback.
- Tampering only `build.sbom_sha256` must invalidate `/api/verify`; test through the real route.
- A changed build commit must produce a different `kid`, while a historical statement signed by the same public key remains verifiable; test the kid derivation/verification boundary.
- Refused, pending, approved, and rejected responses all share the build-bearing statement; extend the existing signed-outcome coverage.
- A missing digest must render safely in the optional UI line; keep the UI change small and localized.

### Task 1: Backend signed provenance and key identity

**Files:**
- Modify: `backend/app/signing.py`
- Modify: `backend/app/orders.py`
- Test: `backend/tests/test_trust.py`

**Interfaces:**
- Produces `signing.signed_build_provenance() -> dict` with exactly `commit`, `ci_run`, `sbom_sha256`, `evidence_status`, and `evidence_url`.
- `signing.KID` is derived from the public key and current `RENDER_GIT_COMMIT`; `verify()` accepts the kid derived from the statement’s own build commit and the pre-feature key-only kid for legacy statements.

- [ ] Write tests for the signed build object, non-waiting live-evidence call, file-fallback exclusion, build-field tampering, and build-derived kid compatibility.
- [ ] Run the focused trust tests and confirm they fail for the missing build field/key behavior.
- [ ] Implement the compact provenance helper, include its single value in `_response()` and its signed statement, and update key derivation/verification.
- [ ] Run focused trust tests until green, then run the full backend suite.

### Task 2: Verifier documentation and safe display

**Files:**
- Modify: `docs/CRACI.md`
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/RunResult.tsx`
- Modify: `frontend/src/copy.ts`
- Modify: `frontend/src/copy.fi.ts`

**Interfaces:**
- The order response type exposes the compact `build` object.
- The order card displays a localized one-line build/digest summary when a signed order response is present, with an explicit LTR island for commit/digest text.

- [ ] Add the three-step “Signed provenance” verifier recipe to `docs/CRACI.md`.
- [ ] Add the compact build type and one safe localized order-card line, using existing typography/tokens.
- [ ] Run the frontend build and inspect the diff for RTL-safe/logical styling.

### Task 3: Final verification

- [ ] Run the exact full backend command from `backend/`.
- [ ] Run `npm run build` from `frontend/` if the UI was touched.
- [ ] Run `git diff --check` and inspect the final diff/status; do not commit or push.
