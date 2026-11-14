"""CRACI evidence summarization and live build evidence fetching."""

from __future__ import annotations

import hashlib
import copy
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
import threading
from threading import Lock
from typing import Iterable


HIGH_RISK_SEVERITIES = {"HIGH", "CRITICAL"}
SEVERITY_RANK = {"HIGH": 1, "CRITICAL": 2}
DEFAULT_REPOSITORY = "omarjku/BengaliPharaohsJunction"
GITHUB_API_BASE_URL = "https://api.github.com"
CRACI_API_BASE_URL = "https://api.craci.com"
TOTAL_TIMEOUT_SECONDS = 10.0
SUCCESS_CACHE_SECONDS = 3600.0
FAILURE_CACHE_SECONDS = 300.0


class EvidenceError(RuntimeError):
    pass


class HttpResponseError(EvidenceError):
    def __init__(self, status_code: int, _detail: str = ""):
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code


class EvidenceTimeout(EvidenceError):
    pass


def _http_get(url: str, headers: dict[str, str], timeout: float) -> bytes:
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        raise HttpResponseError(exc.code) from None
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, TimeoutError):
            raise EvidenceTimeout("request timed out") from None
        raise EvidenceError("request failed") from None
    except TimeoutError:
        raise EvidenceTimeout("request timed out") from None
    except OSError:
        raise EvidenceError("request failed") from None


def _remaining(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise EvidenceTimeout("evidence fetch timed out")
    return remaining


def _json_get(url: str, headers: dict[str, str], deadline: float) -> dict:
    try:
        raw = _http_get(url, headers, _remaining(deadline))
    except TimeoutError:
        raise EvidenceTimeout("request timed out") from None
    except HttpResponseError:
        raise
    except EvidenceError:
        raise
    try:
        payload = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        raise EvidenceError("invalid JSON response") from None
    if not isinstance(payload, dict):
        raise EvidenceError("invalid JSON response")
    return payload


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _unavailable(commit: str | None, reason: str) -> dict:
    return {
        "commit": commit,
        "ci_run": None,
        "craci_job_ids": [],
        "sbom_sha256": None,
        "component_counts": {"pip": 0, "npm": 0},
        "direct_dependencies": [],
        "vulnerabilities": [],
        "blocking_vulnerabilities": [],
        "network_destinations": [],
        "fetched_at": _now(),
        "source": "craci-api-live",
        "status": "unavailable",
        "reason": reason,
    }


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
            from urllib.parse import urlsplit

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
    records: Iterable[tuple[str, dict, bytes]],
    allowlist: set[str],
    warnings: list[str] | None = None,
) -> dict:
    counts = {"pip": 0, "npm": 0}
    direct_dependencies: dict[tuple[str, str, str | None], dict] = {}
    vulnerabilities: dict[tuple[str, str, tuple[str, ...]], dict] = {}
    digest = hashlib.sha256()
    job_ids = []
    for job_id, sbom, raw in records:
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
        "sbom_sha256": digest.hexdigest() if job_ids else None,
        "warnings": list(warnings or []),
    }


def exit_code(summary: dict) -> int:
    return 1 if summary.get("blocking_vulnerabilities") else 0


_CACHE: dict[tuple[str, str | None], tuple[float, dict]] = {}
_CACHE_LOCK = Lock()


def clear_cache() -> None:
    with _CACHE_LOCK:
        _CACHE.clear()
        _REFRESHING.clear()


def _github_headers(token: str) -> dict[str, str]:
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _craci_headers(token: str, accept: str) -> dict[str, str]:
    return {"Accept": accept, "Authorization": f"Bearer {token}"}


def _find_run(repository: str, commit: str, github_token: str, deadline: float) -> dict | None:
    query = urllib.parse.urlencode({"head_sha": commit})
    payload = _json_get(
        f"{GITHUB_API_BASE_URL}/repos/{repository}/actions/runs?{query}",
        _github_headers(github_token),
        deadline,
    )
    runs = payload.get("workflow_runs", [])
    if not isinstance(runs, list):
        raise EvidenceError("invalid GitHub workflow runs")
    candidates = [
        run for run in runs
        if isinstance(run, dict)
        and str(run.get("name", "")).lower() == "ci"
        and run.get("status") in (None, "completed")
        and run.get("conclusion") in (None, "success")
    ]
    preferred = [
        run for run in candidates
        if run.get("event") == "push" and run.get("head_branch") == "main"
    ]
    return (preferred or candidates)[0] if (preferred or candidates) else None


def _run_jobs(repository: str, run_id: str, github_token: str, deadline: float) -> list[dict]:
    jobs: list[dict] = []
    for page in range(1, 11):
        query = urllib.parse.urlencode({"per_page": 100, "page": page})
        payload = _json_get(
            f"{GITHUB_API_BASE_URL}/repos/{repository}/actions/runs/{run_id}/jobs?{query}",
            _github_headers(github_token),
            deadline,
        )
        page_jobs = payload.get("jobs", [])
        if not isinstance(page_jobs, list):
            raise EvidenceError("invalid GitHub jobs")
        jobs.extend(job for job in page_jobs if isinstance(job, dict))
        if len(page_jobs) < 100:
            break
    return jobs


def _craci_evidence(repository: str, job_ids: list[str], token: str, deadline: float) -> tuple[list[tuple[str, dict, bytes]], list[str]]:
    records: list[tuple[str, dict, bytes]] = []
    destinations: set[str] = set()
    query_base = {"provider": "github", "repo": repository}
    for job_id in job_ids:
        query = urllib.parse.urlencode({**query_base, "job_id": job_id})
        try:
            raw = _http_get(
                f"{CRACI_API_BASE_URL}/v1preview1/sbom?{query}",
                _craci_headers(token, "application/vnd.cyclonedx+json; version=1.7"),
                _remaining(deadline),
            )
            sbom = json.loads(raw)
        except TimeoutError:
            raise EvidenceTimeout("request timed out") from None
        except (TypeError, json.JSONDecodeError):
            raise EvidenceError("invalid CRACI SBOM") from None
        if not isinstance(sbom, dict):
            raise EvidenceError("invalid CRACI SBOM")
        records.append((job_id, sbom, raw))
        trace = _json_get(
            f"{CRACI_API_BASE_URL}/v1preview1/network-trace?{query}",
            _craci_headers(token, "application/json"),
            deadline,
        )
        destinations.update(summarize_network_trace(trace))
    return records, sorted(destinations)


def _allowlist() -> set[str]:
    path = Path(__file__).resolve().parents[2] / "scripts" / "craci_allowlist.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    if isinstance(data, list):
        return {str(item) for item in data}
    if isinstance(data, dict):
        values = data.get("ids", data.get("vulnerabilities", []))
        if isinstance(values, list):
            return {str(item.get("id") if isinstance(item, dict) else item) for item in values}
    return set()


def _fetch_uncached(commit: str | None, token: str, repository: str) -> dict:
    if not token:
        return _unavailable(commit, "no_token")
    if not commit:
        return _unavailable(commit, "no_ci_run")
    deadline = time.monotonic() + TOTAL_TIMEOUT_SECONDS
    try:
        run = _find_run(repository, commit, os.getenv("GITHUB_TOKEN", ""), deadline)
    except EvidenceTimeout:
        return _unavailable(commit, "timeout")
    except EvidenceError:
        return _unavailable(commit, "github_error")
    if run is None or run.get("id") is None:
        return _unavailable(commit, "no_ci_run")
    ci_run = str(run["id"])
    try:
        jobs = _run_jobs(repository, ci_run, os.getenv("GITHUB_TOKEN", ""), deadline)
        job_ids = [
            str(job["id"])
            for job in jobs
            if job.get("id") is not None
            and job.get("conclusion") == "success"
            and "craci" in {str(label).lower() for label in job.get("labels") or []}
        ]
    except EvidenceTimeout:
        return _unavailable(commit, "timeout")
    except EvidenceError:
        return _unavailable(commit, "github_error")
    if not job_ids:
        result = _unavailable(commit, "craci_error")
        result["ci_run"] = ci_run
        return result
    try:
        records, destinations = _craci_evidence(repository, job_ids, token, deadline)
    except EvidenceTimeout:
        result = _unavailable(commit, "timeout")
        result["ci_run"] = ci_run
        result["craci_job_ids"] = job_ids
        return result
    except HttpResponseError as exc:
        result = _unavailable(commit, "craci_403" if exc.status_code == 403 else "craci_error")
        result["ci_run"] = ci_run
        result["craci_job_ids"] = job_ids
        return result
    except EvidenceError:
        result = _unavailable(commit, "craci_error")
        result["ci_run"] = ci_run
        result["craci_job_ids"] = job_ids
        return result
    summary = summarize_sboms(records, _allowlist())
    return {
        "commit": commit,
        "ci_run": ci_run,
        "craci_job_ids": job_ids,
        "sbom_sha256": summary["sbom_sha256"],
        "component_counts": summary["component_counts"],
        "direct_dependencies": summary["direct_dependencies"][:30],
        # Public endpoint: counts only, never vulnerability details (security review).
        "vulnerability_counts": {sev.lower(): sum(1 for v in summary["vulnerabilities"] if v.get("severity") == sev)
                                 for sev in ("HIGH", "CRITICAL")},
        "blocking_vulnerability_count": len(summary["blocking_vulnerabilities"]),
        "network_destinations": destinations,
        "fetched_at": _now(),
        "source": "craci-api-live",
        "status": "ok",
    }


_REFRESHING: set[tuple[str, str | None]] = set()


def _store(key: tuple[str, str | None], result: dict) -> None:
    ttl = SUCCESS_CACHE_SECONDS if result["status"] == "ok" else FAILURE_CACHE_SECONDS
    with _CACHE_LOCK:
        _CACHE[key] = (time.monotonic() + ttl, result)
        _REFRESHING.discard(key)


def _refresh(key: tuple[str, str | None], commit: str | None, token: str, repository: str) -> dict:
    try:
        result = _fetch_uncached(commit, token, repository)
    except Exception:  # noqa: BLE001 - never let a background refresh die silently with the flag set
        result = _unavailable(commit, "craci_error")
    _store(key, result)
    return result


def fetch_live_evidence(commit: str | None, token: str, repository: str = DEFAULT_REPOSITORY,
                        wait: bool = True) -> dict:
    """Cached live evidence. The lock is never held during network I/O (security review). With wait=False (public
    pages), a miss starts ONE background refresh and returns the stale result or `refreshing` at once."""
    key = (repository, commit)
    now = time.monotonic()
    with _CACHE_LOCK:
        cached = _CACHE.get(key)
        if cached and cached[0] > now:
            return copy.deepcopy(cached[1])
        stale = copy.deepcopy(cached[1]) if cached else None
        start = key not in _REFRESHING
        if start:
            _REFRESHING.add(key)
    if wait:
        return copy.deepcopy(_refresh(key, commit, token, repository) if start
                             else _fetch_uncached(commit, token, repository))
    if start:
        threading.Thread(target=_refresh, args=(key, commit, token, repository), daemon=True).start()
    return stale or _unavailable(commit, "refreshing")
