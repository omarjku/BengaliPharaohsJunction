import hashlib
import json

import pytest

from scripts import craci_sbom


def _sbom():
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.7",
        "metadata": {"component": {"bom-ref": "pkg:pypi/app@1.0.0"}},
        "components": [
            {"bom-ref": "pkg:pypi/requests@2.32.0", "name": "requests", "version": "2.32.0",
             "purl": "pkg:pypi/requests@2.32.0"},
            {"bom-ref": "pkg:pypi/urllib3@2.2.2", "name": "urllib3", "version": "2.2.2",
             "purl": "pkg:pypi/urllib3@2.2.2"},
            {"bom-ref": "pkg:npm/react@18.3.1", "name": "react", "version": "18.3.1",
             "purl": "pkg:npm/react@18.3.1"},
        ],
        "dependencies": [{
            "ref": "pkg:pypi/app@1.0.0",
            "dependsOn": ["pkg:pypi/requests@2.32.0", "pkg:npm/react@18.3.1"],
        }],
        "vulnerabilities": [{
            "id": "CVE-2026-0001",
            "ratings": [{"severity": "high"}],
            "affects": [{"ref": "pkg:pypi/requests@2.32.0"}],
        }],
    }


def test_fetch_sbom_reads_a_recorded_api_response(monkeypatch):
    payload = _sbom()

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return json.dumps(payload).encode()

    def fake_urlopen(request, timeout):
        assert request.full_url.endswith("/v1preview1/sbom?provider=github&repo=acme%2Fshop&job_id=123")
        assert request.get_header("Authorization") == "Bearer test-token"
        assert timeout == craci_sbom.API_TIMEOUT_SECONDS
        return FakeResponse()

    monkeypatch.setattr(craci_sbom.urllib.request, "urlopen", fake_urlopen)

    assert craci_sbom.fetch_sbom("acme/shop", "123", "test-token") == payload


def test_summary_counts_ecosystems_direct_dependencies_and_digest():
    raw = json.dumps(_sbom(), separators=(",", ":")).encode()
    summary = craci_sbom.summarize_sboms([("123", _sbom(), raw)], allowlist=set())

    assert summary["component_counts"] == {"pip": 2, "npm": 1}
    assert summary["direct_dependencies"] == [
        {"ecosystem": "pip", "name": "requests", "version": "2.32.0"},
        {"ecosystem": "npm", "name": "react", "version": "18.3.1"},
    ]
    expected_hash = hashlib.sha256(b"123\0" + raw).hexdigest()
    assert summary["sbom_sha256"] == expected_hash
    assert summary["blocking_vulnerabilities"][0]["id"] == "CVE-2026-0001"


def test_allowlisted_high_vulnerability_does_not_fail():
    summary = craci_sbom.summarize_sboms([("123", _sbom(), b"recorded")], allowlist={"CVE-2026-0001"})

    assert summary["blocking_vulnerabilities"] == []
    assert craci_sbom.exit_code(summary) == 0


def test_critical_rating_takes_precedence_over_high_rating():
    sbom = _sbom()
    sbom["vulnerabilities"][0]["ratings"].append({"severity": "critical"})

    summary = craci_sbom.summarize_sboms([("123", sbom, b"recorded")], allowlist=set())

    assert summary["vulnerabilities"][0]["severity"] == "CRITICAL"


def test_api_failure_is_a_warning_not_a_vulnerability_failure():
    summary = craci_sbom.summarize_sboms([], allowlist=set(), warnings=["CRACI API unavailable"])

    assert summary["warnings"] == ["CRACI API unavailable"]
    assert craci_sbom.exit_code(summary) == 0


def test_network_trace_collects_http_dns_and_ssh_destinations():
    trace = {
        "observations": [
            {"protocol": "http", "http": {"originUrl": "https://pypi.org/simple/pkg", "policyDenied": False}},
            {"protocol": "dns", "dns": {"record": "registry.npmjs.org A", "response": "203.0.113.10"}},
            {"protocol": "ssh_git", "sshGit": {"host": "github.com", "allowed": True}},
        ]
    }

    assert craci_sbom.summarize_network_trace(trace) == ["github.com", "pypi.org", "registry.npmjs.org"]
