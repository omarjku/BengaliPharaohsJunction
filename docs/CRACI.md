# CRACI evidence for TRUSTED trade

CRACI is part of the trust boundary behind every signed order. CI still runs on
the `craci` runner and keeps its provenance job, but the deployed API now
fetches the evidence for its own Render build lazily from outside the CRACI
runner network.

## Why the API fetch is live

Calls to `https://api.craci.com` made inside CRACI runners receive Envoy's
`403 Access denied`, including calls with a fake bearer token. The same API is
reachable from outside: a fake token receives the normal `401` response. The
runner restriction means CI cannot be the authoritative fetcher, so Render
uses `RENDER_GIT_COMMIT` and `CRACI_API_TOKEN` to fetch the deployed commit's
evidence on first request. The token is never returned or included in an error.

## How it works

For the Render commit, the API calls GitHub's unauthenticated
`GET /repos/omarjku/BengaliPharaohsJunction/actions/runs?head_sha=<sha>` (using
`GITHUB_TOKEN` when available), selects the `CI` workflow with a successful
push to `main` preferred, and lists its successful jobs whose labels include
`craci`. For each job it fetches:

- `GET /v1preview1/sbom?provider=github&repo=OWNER/REPO&job_id=N` with CycloneDX 1.7 `Accept`;
- `GET /v1preview1/network-trace?provider=github&repo=OWNER/REPO&job_id=N`.

Both CRACI requests use `Authorization: Bearer $CRACI_API_TOKEN`. The total
fetch deadline is about 10 seconds. Successful results are cached in memory
for one hour; unavailable results are cached for five minutes. Fetching is
lazy, so startup never waits on GitHub or CRACI. `BUILD_PROVENANCE_PATH` is
used as a fallback when live evidence is unavailable.

## Build response

`GET /.well-known/front-door-build.json` returns an object with:

```json
{
  "commit": "<Render commit>",
  "ci_run": "<GitHub run id>",
  "craci_job_ids": ["<job id>"],
  "sbom_sha256": "<digest>",
  "component_counts": {"pip": 37, "npm": 214},
  "direct_dependencies": [{"ecosystem": "pip", "name": "httpx", "version": "..."}],
  "vulnerability_counts": {"high": 0, "critical": 0},
  "blocking_vulnerability_count": 0,
  "network_destinations": ["api.github.com", "pypi.org"],
  "fetched_at": "2026-11-14T12:34:56Z",
  "source": "craci-api-live",
  "status": "ok"
}
```

`direct_dependencies` is limited to the first 30. `vulnerability_counts` counts known HIGH/CRITICAL findings and `blocking_vulnerability_count` excludes IDs in
`scripts/craci_allowlist.json`. When unavailable, `status` is
`"unavailable"` and `reason` is one of `no_token`, `no_ci_run`, `craci_403`,
`craci_error`, `github_error`, or `timeout`. The signing-keys document keeps
the same object in its `build` field.

## What CRACI's network trace taught us

The trace included `generativelanguage.googleapis.com`. The CI workflow did not
explicitly set `GEMINI_API_KEY`, so a runner-level key could make a backend route
call Gemini even though the ordinary tests replace Gemini with fakes. The
`backend-tests / Run backend tests` step is the affected surface: the backend
has real Gemini REST clients for agent, rules, vision, and voice. The
`packages-tests / Run package tests` step uses replay fixtures for the compiler;
`compiler/tests/record_fixtures.py` is a manual recorder, not a pytest test, and
the provenance step only calls GitHub and CRACI.

Both test steps now set `GEMINI_API_KEY` to an explicit empty string; package
tests also set `LLM_MODE=replay`. A real Gemini call is an explicit local/demo
action, never an ambient CI side effect.

## The door defends itself using CRACI evidence

With `BUILD_TRUST_GATE=1` (the default), the front door reads only its
unexpired in-memory CRACI evidence cache. If cached evidence has status `ok`
and one or more non-allowlisted HIGH/CRITICAL findings, an otherwise automatic
order becomes `pending_approval` with reason code `BUILD_NOT_TRUSTED`; a human
can approve orders while the build is repaired. Zero findings leave automatic
orders unchanged. Missing, expired, or refreshing evidence is `unavailable`
and does not block ordering, and the trust check never waits for network I/O.

## What CRACI found and what we did

The build at `8958ae5` reported 7 HIGH and 0 CRITICAL findings. Local audits
map those HIGH findings to these runtime dependencies (Starlette is transitive
through FastAPI):

| Package | Installed | Advisory | Fixed in | Scope |
| --- | --- | --- | --- | --- |
| `cryptography` | 44.0.0 | CVE-2024-12797 | 44.0.1 | runtime |
| `cryptography` | 44.0.0 | CVE-2026-26007 | 46.0.5 | runtime |
| `cryptography` | 44.0.0 | CVE-2026-69247 | 50.0.0 | runtime |
| `cryptography` | 44.0.0 | CVE-2026-69249 | 49.0.0 | runtime |
| `starlette` | 0.46.2 | CVE-2025-62727 | 0.49.1 | runtime |
| `starlette` | 0.46.2 | CVE-2026-48818 | 1.1.0 | runtime |
| `starlette` | 0.46.2 | CVE-2026-54283 | 1.3.1 | runtime |

We upgraded `fastapi` 0.115.12 → 0.133.0 so the framework accepts the fixed
Starlette line, pinned `starlette` to 1.3.1, and upgraded `cryptography`
44.0.0 → 50.0.0. Fresh-environment backend and package tests remain green.
The post-fix local audits show 0 HIGH/CRITICAL: pip-audit still reports the
lower-severity `python-dotenv` 1.1.0 finding (fixed in 1.2.2) and dev/test
`pytest` 8.3.5 finding (fixed in 9.0.3); npm audit still reports 7 moderate
`typescript-eslint`/`minimatch` entries and offers no non-forced fix. We did
not use a forced npm override. The fixes are deployed. On Sun 15 Nov the live
evidence for commit `76f5a92` (CI run `43687055766`) reported status `ok`, 170 pip
and 181 npm components, 19 network destinations, and still 7 HIGH / 0 CRITICAL
findings (7 blocking; the allowlist is empty). We have not yet traced why CRACI's
count differs from the local audits. With the build-trust gate on (the default),
any otherwise automatic order is held for a human (`BUILD_NOT_TRUSTED`) while that
evidence is cached.

## Verifying the digest

Use `craci_job_ids` in the order returned. Fetch each raw CycloneDX SBOM, then
initialize SHA-256 and, for every job, update it with the UTF-8 job ID, one NUL
byte (`0x00`), and the exact raw SBOM response bytes. The final hexadecimal
digest must equal `sbom_sha256`:

```python
digest = hashlib.sha256()
for job_id in craci_job_ids:
    digest.update(job_id.encode("utf-8"))
    digest.update(b"\0")
    digest.update(raw_sbom_bytes[job_id])
assert digest.hexdigest() == build["sbom_sha256"]
```

Inspect the network trace destinations and vulnerability lists separately;
the digest covers SBOM bytes only. A missing or failed fetch is reported as
unavailable, never silently presented as verified.

## Signed provenance

To prove which audited build signed an order:

1. Verify the order's `signed_statement` and `signature` with `POST /api/verify` (or the Ed25519 key in `/.well-known/front-door-keys.json`). Continue only when the result is `valid: true`.
2. Read `signed_statement.build.commit` and `signed_statement.build.sbom_sha256`; these values are covered by the order signature.
3. Fetch `signed_statement.build.evidence_url` (`/.well-known/front-door-build.json`) and compare its `commit` and `sbom_sha256` to the signed values. If `evidence_status` is `unavailable`, the signed commit remains identifiable but the missing digest is not evidence of a verified SBOM.


## Security notes
- The public endpoint publishes integrity data and vulnerability **counts** only, never vulnerability details.
- Public pages never wait on GitHub or CRACI: a cache miss starts one background refresh and the page returns the cached result or `status: unavailable, reason: refreshing` at once. The cache lock is never held during network calls.
