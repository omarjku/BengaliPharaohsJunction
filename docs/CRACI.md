# CRACI evidence for TRUSTED trade

CRACI is part of the trust boundary behind every signed order, not just the runner label in CI. The existing test and build jobs already run on `craci`; the `provenance` job waits for them on pushes to `main`, fetches the terminal evidence for this GitHub run, and uploads `build-provenance.json` plus `craci-sbom-summary.json`.

## What we use

The script uses the CRACI API with `Authorization: Bearer $CRACI_API_TOKEN`:

- `GET /v1preview1/sbom?provider=github&repo=OWNER/REPOSITORY&job_id=...` — CycloneDX 1.7 SBOM per completed GitHub job.
- `GET /v1preview1/network-trace?provider=github&repo=OWNER/REPOSITORY&job_id=...` — observed HTTP, DNS, TCP, and SSH destinations.

GitHub's run-jobs API provides the terminal numeric job IDs because CRACI's documented `/v1preview1/jobs?status=active` endpoint lists active jobs only. The script selects successful jobs from the current `GITHUB_RUN_ID`, aggregates pip/npm components and direct dependencies, and hashes the ordered response bytes (job ID + raw SBOM) with SHA-256. API errors are warnings; only a known HIGH/CRITICAL vulnerability not listed in `scripts/craci_allowlist.json` fails the job.

The network trace is evidence, not a claim that every build only contacts PyPI/npm: the trace may also show GitHub, CRACI, or other observed services. The fetched OpenAPI exposes no AI-fix endpoint, so AI fixes are deliberately documented as a next step rather than guessed into CI.

## Example output

```text
## CRACI supply-chain evidence
- SBOM SHA-256: `4c8d…91af`
- CRACI job IDs: `8012345678,8012345679,8012345680`
- Components: pip `37`, npm `214`
- Direct dependencies: 18
- Network destinations: `api.github.com`, `github.com`, `pypi.org`, `registry.npmjs.org`
```

`build-provenance.json` has this shape:

```json
{
  "commit": "<GITHUB_SHA>",
  "ci_run": "<GITHUB_RUN_ID>",
  "craci_build_id": "8012345678,8012345679,8012345680",
  "sbom_sha256": "<sha256>",
  "generated_at": "2026-11-14T12:34:56Z"
}
```

## How a judge can verify it

1. Download the `craci-provenance` artifact from the successful main-branch run and inspect both JSON files. Confirm `commit` is the judged commit and that `sbom_sha256` matches the summary.
2. Fetch `https://<front-door>/.well-known/front-door-build.json`. It is read-only and falls back safely to `{ "commit": "<RENDER_GIT_COMMIT>", "sbom": "unavailable" }` when Render has no artifact mounted. On a deployed build, compare its fields with the artifact.
3. Fetch `https://<front-door>/.well-known/front-door-keys.json`. The additive `build` field identifies the same provenance document alongside the Ed25519 JWK used to verify the signed order. Existing signature verification remains unchanged: canonicalize the `signed_statement`, verify the signature selected by `kid`, then compare the statement's deployment build to the public build document.
4. Use each numeric ID in `craci_build_id` with the two CRACI endpoints above and the repository/run metadata. Recompute the ordered SHA-256 over `job_id`, a NUL byte, and each raw SBOM response to independently verify the recorded digest. Inspect the network trace destinations and the vulnerability list; an allowlisted finding is explicit in `scripts/craci_allowlist.json`.

CRACI API outages do not turn `main` red. That keeps provenance honest: a missing proof is reported as unavailable, never silently presented as verified.
