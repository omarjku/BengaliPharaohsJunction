import hashlib
import json

import pytest

from app import craci_evidence


REPOSITORY = "omarjku/BengaliPharaohsJunction"
TOKEN = "super-secret-token"


def _sbom(raw_marker: str) -> bytes:
    return json.dumps({
        "metadata": {"component": {"bom-ref": f"pkg:pypi/app@{raw_marker}"}},
        "components": [{
            "bom-ref": f"pkg:pypi/requests@{raw_marker}",
            "name": "requests",
            "version": raw_marker,
            "purl": f"pkg:pypi/requests@{raw_marker}",
        }],
        "dependencies": [{
            "ref": f"pkg:pypi/app@{raw_marker}",
            "dependsOn": [f"pkg:pypi/requests@{raw_marker}"],
        }],
    }, separators=(",", ":")).encode()


@pytest.fixture(autouse=True)
def clear_live_cache():
    craci_evidence.clear_cache()
    yield
    craci_evidence.clear_cache()


def _mock_success(monkeypatch, *, calls=None):
    raw_sboms = {"20": _sbom("2.0"), "10": _sbom("1.0")}
    runs_url_part = "/actions/runs?head_sha=commit-1"

    def fake_get(url, headers, timeout):
        if calls is not None:
            calls.append((url, headers, timeout))
        if runs_url_part in url:
            return json.dumps({"workflow_runs": [{
                "id": 42, "name": "CI", "event": "push", "head_branch": "main",
                "status": "completed", "conclusion": "success",
            }]}).encode()
        if "/actions/runs/42/jobs" in url:
            return json.dumps({"jobs": [
                {"id": 20, "labels": ["craci", "ubuntu"], "conclusion": "success"},
                {"id": 10, "labels": ["craci"], "conclusion": "success"},
                {"id": 99, "labels": ["ubuntu"], "conclusion": "success"},
            ]}).encode()
        if "/sbom?" in url:
            job_id = url.split("job_id=")[1]
            return raw_sboms[job_id]
        if "/network-trace?" in url:
            return json.dumps({"observations": [{
                "protocol": "http", "http": {"originUrl": "https://pypi.org/simple"},
            }]}).encode()
        raise AssertionError(url)

    monkeypatch.setattr(craci_evidence, "_http_get", fake_get)
    return raw_sboms


def test_live_fetch_summarizes_github_jobs_and_craci_evidence(monkeypatch):
    raw_sboms = _mock_success(monkeypatch)

    result = craci_evidence.fetch_live_evidence("commit-1", TOKEN, REPOSITORY)

    assert result["status"] == "ok"
    assert result["source"] == "craci-api-live"
    assert result["commit"] == "commit-1"
    assert result["ci_run"] == "42"
    assert result["craci_job_ids"] == ["20", "10"]
    assert result["component_counts"] == {"pip": 2, "npm": 0}
    assert result["direct_dependencies"] == [
        {"ecosystem": "pip", "name": "requests", "version": "2.0"},
        {"ecosystem": "pip", "name": "requests", "version": "1.0"},
    ]
    assert result["network_destinations"] == ["pypi.org"]
    assert result["sbom_sha256"] == hashlib.sha256(
        b"20\0" + raw_sboms["20"] + b"10\0" + raw_sboms["10"]
    ).hexdigest()
    assert "reason" not in result


def test_craci_403_is_unavailable_without_token_leak(monkeypatch, caplog):
    def fake_get(url, headers, timeout):
        if "/actions/runs?" in url:
            return json.dumps({"workflow_runs": [{
                "id": 42, "name": "CI", "event": "push", "head_branch": "main",
                "status": "completed", "conclusion": "success",
            }]}).encode()
        if "/actions/runs/42/jobs" in url:
            return json.dumps({"jobs": [{
                "id": 20, "labels": ["craci"], "conclusion": "success",
            }]}).encode()
        raise craci_evidence.HttpResponseError(403, f"Bearer {TOKEN}")

    monkeypatch.setattr(craci_evidence, "_http_get", fake_get)

    result = craci_evidence.fetch_live_evidence("commit-1", TOKEN, REPOSITORY)

    text = json.dumps(result) + " " + caplog.text
    assert result["status"] == "unavailable"
    assert result["reason"] == "craci_403"
    assert TOKEN not in text


def test_no_ci_run_is_unavailable(monkeypatch):
    monkeypatch.setattr(craci_evidence, "_http_get", lambda url, headers, timeout: b'{"workflow_runs": []}')

    result = craci_evidence.fetch_live_evidence("commit-1", TOKEN, REPOSITORY)

    assert result["status"] == "unavailable"
    assert result["reason"] == "no_ci_run"


def test_no_token_does_not_make_http_request(monkeypatch):
    called = []
    monkeypatch.setattr(craci_evidence, "_http_get", lambda *args: called.append(args))

    result = craci_evidence.fetch_live_evidence("commit-1", "", REPOSITORY)

    assert result["status"] == "unavailable"
    assert result["reason"] == "no_token"
    assert called == []


def test_success_is_cached(monkeypatch):
    calls = []
    _mock_success(monkeypatch, calls=calls)

    first = craci_evidence.fetch_live_evidence("commit-1", TOKEN, REPOSITORY)
    second = craci_evidence.fetch_live_evidence("commit-1", TOKEN, REPOSITORY)

    assert second == first
    assert len(calls) == 6


def test_public_path_never_waits_and_starts_one_refresh(monkeypatch):
    import threading
    craci_evidence.clear_cache()
    gate = threading.Event()
    started = []

    def slow(commit, token, repository):
        started.append(commit)
        gate.wait(5)
        return {"status": "ok", "commit": commit}

    monkeypatch.setattr(craci_evidence, "_fetch_uncached", slow)
    first = craci_evidence.fetch_live_evidence("commit-9", TOKEN, REPOSITORY, wait=False)
    second = craci_evidence.fetch_live_evidence("commit-9", TOKEN, REPOSITORY, wait=False)
    assert first["status"] == "unavailable" and first["reason"] == "refreshing"
    assert second["reason"] == "refreshing"
    gate.set()
    for _ in range(50):
        if craci_evidence._CACHE.get((REPOSITORY, "commit-9")):
            break
        threading.Event().wait(0.02)
    assert started == ["commit-9"]  # one background refresh, not one per request
    assert craci_evidence.fetch_live_evidence("commit-9", TOKEN, REPOSITORY, wait=False)["status"] == "ok"


def test_public_output_has_vulnerability_counts_not_details(monkeypatch):
    _mock_success(monkeypatch, calls=[])
    result = craci_evidence.fetch_live_evidence("commit-1", TOKEN, REPOSITORY)
    assert "vulnerabilities" not in result and "blocking_vulnerabilities" not in result
    assert set(result["vulnerability_counts"]) == {"high", "critical"}
    assert isinstance(result["blocking_vulnerability_count"], int)
