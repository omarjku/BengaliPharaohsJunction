#!/usr/bin/env python3
"""Summarize CRACI evidence for the current GitHub Actions run."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.craci_evidence import exit_code, summarize_network_trace, summarize_sboms

API_BASE_URL = "https://api.craci.com"
GITHUB_API_BASE_URL = "https://api.github.com"
API_TIMEOUT_SECONDS = 20
HIGH_RISK_SEVERITIES = {"HIGH", "CRITICAL"}
SEVERITY_RANK = {"HIGH": 1, "CRITICAL": 2}


class CraciAPIError(RuntimeError):
    pass


def _get(url: str, token: str, accept: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"Accept": accept, "Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=API_TIMEOUT_SECONDS) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read() or b""
        except OSError:
            body = b""
        try:
            problem = json.loads(body or b"{}")
            detail = str(problem.get("detail") or problem.get("title") or "")[:200]
        except (ValueError, AttributeError):
            detail = body.decode("utf-8", "replace").strip()[:160]
        detail += f" [server={exc.headers.get('server', '?')}]" if exc.headers else ""
        raise CraciAPIError(f"API returned HTTP {exc.code}" + (f": {detail}" if detail else "")) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise CraciAPIError("API request failed") from None


def _get_json(url: str, token: str, accept: str = "application/json") -> tuple[dict, bytes]:
    raw = _get(url, token, accept)
    try:
        return json.loads(raw), raw
    except json.JSONDecodeError:
        raise CraciAPIError("API returned invalid JSON") from None


def fetch_sbom(repository: str, job_id: str, token: str) -> dict:
    query = urllib.parse.urlencode({"provider": "github", "repo": repository, "job_id": job_id})
    payload, _ = _get_json(
        f"{API_BASE_URL}/v1preview1/sbom?{query}",
        token,
        "application/vnd.cyclonedx+json; version=1.7",
    )
    return payload


def fetch_network_trace(repository: str, job_id: str, token: str) -> dict:
    query = urllib.parse.urlencode({"provider": "github", "repo": repository, "job_id": job_id})
    payload, _ = _get_json(f"{API_BASE_URL}/v1preview1/network-trace?{query}", token)
    return payload


def fetch_run_jobs(repository: str, run_id: str, token: str) -> list[dict]:
    """Use GitHub's run-jobs API because CRACI exposes only active-job discovery."""
    jobs: list[dict] = []
    for page in range(1, 11):
        query = urllib.parse.urlencode({"per_page": 100, "page": page})
        url = f"{GITHUB_API_BASE_URL}/repos/{repository}/actions/runs/{run_id}/jobs?{query}"
        payload, _ = _get_json(url, token, "application/vnd.github+json")
        page_jobs = payload.get("jobs", [])
        if not isinstance(page_jobs, list):
            raise CraciAPIError("GitHub returned an invalid jobs list")
        jobs.extend(job for job in page_jobs if isinstance(job, dict))
        if len(page_jobs) < 100:
            break
    return jobs


def _allowlist(path: Path) -> set[str]:
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return set()
    if isinstance(data, list):
        return {str(item) for item in data}
    if isinstance(data, dict):
        values = data.get("ids", data.get("vulnerabilities", []))
        if isinstance(values, list):
            return {str(item.get("id") if isinstance(item, dict) else item) for item in values}
    return set()


def _job_ids(repository: str, run_id: str, sha: str, token: str, warnings: list[str]) -> list[str]:
    configured = os.getenv("CRACI_JOB_IDS") or os.getenv("CRACI_JOB_ID")
    if configured:
        return [job_id.strip() for job_id in configured.split(",") if job_id.strip()]
    if not token:
        warnings.append("GITHUB_TOKEN is unavailable; cannot discover terminal CRACI job IDs")
        return []
    try:
        jobs = fetch_run_jobs(repository, run_id, token)
    except CraciAPIError as exc:
        warnings.append(f"GitHub job discovery warning: {exc}")
        return []
    selected = []
    for job in jobs:
        if str(job.get("run_id", run_id)) != str(run_id):
            continue
        if "craci" not in [str(label).lower() for label in job.get("labels") or []]:
            continue
        if job.get("conclusion") == "success" and job.get("id") is not None:
            selected.append(str(job["id"]))
    if not selected:
        warnings.append(f"No finished CRACI jobs found in run {run_id} ({len(jobs)} jobs listed)")
    return selected


def _write_step_summary(summary: dict, path: str) -> None:
    lines = [
        "## CRACI supply-chain evidence",
        "",
        f"- SBOM SHA-256: `{summary.get('sbom_sha256') or 'unavailable'}`",
        f"- CRACI job IDs: `{summary.get('craci_build_id') or 'unavailable'}`",
        f"- Components: pip `{summary['component_counts']['pip']}`, npm `{summary['component_counts']['npm']}`",
        f"- Direct dependencies: {len(summary['direct_dependencies'])}",
        f"- Network destinations: {', '.join(f'`{host}`' for host in summary.get('network_destinations', [])) or 'unavailable'}",
    ]
    if summary["vulnerabilities"]:
        lines.extend(["", "### HIGH/CRITICAL vulnerabilities"])
        lines.extend(f"- {item['severity']}: `{item['id']}`" for item in summary["vulnerabilities"])
    if summary["blocking_vulnerabilities"]:
        lines.extend(["", "Blocking vulnerability findings are not allowlisted."])
    if summary["warnings"]:
        lines.extend(["", "### Warnings"])
        lines.extend(f"- {warning}" for warning in summary["warnings"])
    with open(path, "a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def main() -> int:
    repository = os.getenv("GITHUB_REPOSITORY", "")
    run_id = os.getenv("GITHUB_RUN_ID", "")
    sha = os.getenv("GITHUB_SHA", "")
    craci_token = os.getenv("CRACI_API_TOKEN", "")
    github_token = os.getenv("GITHUB_TOKEN", "")
    warnings: list[str] = []
    if not craci_token:
        warnings.append("CRACI_API_TOKEN is unavailable; CRACI evidence was not fetched")
    job_ids = _job_ids(repository, run_id, sha, github_token, warnings) if craci_token else []
    records: list[tuple[str, dict, bytes]] = []
    network_destinations: set[str] = set()
    for job_id in job_ids:
        try:
            query = urllib.parse.urlencode({"provider": "github", "repo": repository, "job_id": job_id})
            raw = _get(
                f"{API_BASE_URL}/v1preview1/sbom?{query}",
                craci_token,
                "application/vnd.cyclonedx+json; version=1.7",
            )
            records.append((job_id, json.loads(raw), raw))
        except (CraciAPIError, json.JSONDecodeError) as exc:
            warnings.append(f"CRACI SBOM unavailable for job {job_id}: {exc}")
        try:
            network_destinations.update(summarize_network_trace(fetch_network_trace(repository, job_id, craci_token)))
        except CraciAPIError as exc:
            warnings.append(f"CRACI network trace unavailable for job {job_id}: {exc}")
    summary = summarize_sboms(records, _allowlist(Path(__file__).with_name("craci_allowlist.json")), warnings)
    summary["repository"] = repository or None
    summary["commit"] = sha or None
    summary["ci_run"] = run_id or None
    summary["network_destinations"] = sorted(network_destinations)
    output_path = os.getenv("CRACI_SUMMARY_PATH", "craci-sbom-summary.json")
    Path(output_path).write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    step_summary = os.getenv("GITHUB_STEP_SUMMARY")
    if step_summary:
        _write_step_summary(summary, step_summary)
    print(f"CRACI SBOM summary written to {output_path}")
    return exit_code(summary)


if __name__ == "__main__":
    sys.exit(main())
