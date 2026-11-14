#!/usr/bin/env python3
"""Summarize CRACI evidence for the current GitHub Actions run."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

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
        raise CraciAPIError(f"API returned HTTP {exc.code}") from None
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


def _ecosystem(component: dict) -> str | None:
    purl = str(component.get("purl", ""))
    if purl.startswith("pkg:pypi/"):
        return "pip"
    if purl.startswith("pkg:npm/"):
        return "npm"
    return None


def _component_record(component: dict) -> dict | None:
    ecosystem = _ecosystem(component)
    if ecosystem is None:
        return None
    return {
        "ecosystem": ecosystem,
        "name": component.get("name") or component.get("purl"),
        "version": component.get("version"),
    }


def _direct_dependencies(sbom: dict) -> list[dict]:
    components = {
        component.get("bom-ref"): component
        for component in sbom.get("components", [])
        if isinstance(component, dict) and component.get("bom-ref")
    }
    root = (sbom.get("metadata") or {}).get("component") or {}
    root_ref = root.get("bom-ref")
    direct_refs: list[str] = []
    for dependency in sbom.get("dependencies", []):
        if isinstance(dependency, dict) and dependency.get("ref") == root_ref:
            direct_refs.extend(ref for ref in dependency.get("dependsOn", []) if isinstance(ref, str))
            break
    records = []
    for ref in direct_refs:
        component = components.get(ref)
        if component is None:
            continue
        record = _component_record(component)
        if record is not None:
            records.append(record)
    return records


def _vulnerabilities(sbom: dict) -> list[dict]:
    found: list[dict] = []
    entries = [(vulnerability, None) for vulnerability in sbom.get("vulnerabilities", [])]
    for component in sbom.get("components", []):
        if isinstance(component, dict):
            entries.extend((vulnerability, component.get("bom-ref"))
                           for vulnerability in component.get("vulnerabilities", []))
    for vulnerability, component_ref in entries:
        if not isinstance(vulnerability, dict):
            continue
        severities = {
            str(rating.get("severity", "")).upper()
            for rating in vulnerability.get("ratings", [])
            if isinstance(rating, dict)
        }
        if vulnerability.get("severity"):
            severities.add(str(vulnerability["severity"]).upper())
        severe = sorted(severities & HIGH_RISK_SEVERITIES)
        if not severe:
            continue
        affected = sorted({
            str(item.get("ref"))
            for item in vulnerability.get("affects", [])
            if isinstance(item, dict) and item.get("ref")
        })
        if component_ref and component_ref not in affected:
            affected.append(component_ref)
        found.append({
            "id": str(vulnerability.get("id") or "unknown"),
            "severity": max(severe, key=SEVERITY_RANK.__getitem__),
            "affects": affected,
            "source": vulnerability.get("source"),
            "recommendation": vulnerability.get("recommendation"),
        })
    return found


def summarize_network_trace(trace: dict) -> list[str]:
    destinations: set[str] = set()
    for observation in trace.get("observations", []):
        if not isinstance(observation, dict):
            continue
        protocol = observation.get("protocol")
        detail_key = {"ssh_git": "sshGit"}.get(protocol, protocol)
        details = observation.get(detail_key, {}) if detail_key else {}
        if not isinstance(details, dict):
            continue
        if protocol == "http":
            hostname = urlsplit(str(details.get("originUrl", ""))).hostname
            if hostname:
                destinations.add(hostname)
        elif protocol == "dns":
            record = str(details.get("record", ""))
            if record:
                destinations.add(record.split()[0].rstrip("."))
        elif protocol == "ssh_git" and details.get("host"):
            destinations.add(str(details["host"]))
        elif protocol == "tcp":
            destinations.update(str(host) for host in details.get("resolvedHosts", []) if host)
            if details.get("tlsServerName"):
                destinations.add(str(details["tlsServerName"]))
    return sorted(destinations)


def summarize_sboms(
    records: list[tuple[str, dict, bytes]],
    allowlist: set[str],
    warnings: list[str] | None = None,
) -> dict:
    counts = {"pip": 0, "npm": 0}
    direct_dependencies: dict[tuple[str, str, str | None], dict] = {}
    vulnerabilities: dict[tuple[str, str, tuple[str, ...]], dict] = {}
    digest = hashlib.sha256()
    job_ids = []
    for job_id, sbom, raw in sorted(records, key=lambda item: item[0]):
        job_ids.append(job_id)
        digest.update(job_id.encode())
        digest.update(b"\0")
        digest.update(raw)
        for component in sbom.get("components", []):
            if isinstance(component, dict):
                ecosystem = _ecosystem(component)
                if ecosystem in counts:
                    counts[ecosystem] += 1
        for dependency in _direct_dependencies(sbom):
            key = (dependency["ecosystem"], dependency["name"], dependency["version"])
            direct_dependencies[key] = dependency
        for vulnerability in _vulnerabilities(sbom):
            key = (vulnerability["id"], vulnerability["severity"], tuple(vulnerability["affects"]))
            vulnerabilities[key] = vulnerability
    known_vulnerabilities = sorted(vulnerabilities.values(), key=lambda item: (item["severity"], item["id"]))
    return {
        "job_ids": job_ids,
        "craci_build_id": ",".join(job_ids) if job_ids else None,
        "component_counts": counts,
        "direct_dependencies": sorted(
            direct_dependencies.values(),
            key=lambda item: ({"pip": 0, "npm": 1}.get(item["ecosystem"], 2), item["name"]),
        ),
        "vulnerabilities": known_vulnerabilities,
        "blocking_vulnerabilities": [item for item in known_vulnerabilities if item["id"] not in allowlist],
        "sbom_sha256": digest.hexdigest() if records else None,
        "warnings": list(warnings or []),
    }


def exit_code(summary: dict) -> int:
    return 1 if summary.get("blocking_vulnerabilities") else 0


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
