import json

from fastapi.testclient import TestClient

from app import signing
from app.main import app


c = TestClient(app)


def test_build_provenance_has_safe_fallback(monkeypatch):
    monkeypatch.delenv("BUILD_PROVENANCE_PATH", raising=False)
    monkeypatch.setenv("RENDER_GIT_COMMIT", "render-commit")
    unavailable = {
        "commit": "render-commit", "ci_run": None, "craci_job_ids": [], "sbom_sha256": None,
        "component_counts": {"pip": 0, "npm": 0}, "direct_dependencies": [], "vulnerabilities": [],
        "blocking_vulnerabilities": [], "network_destinations": [], "fetched_at": "now",
        "source": "craci-api-live", "status": "unavailable", "reason": "no_token",
    }
    monkeypatch.setattr(signing.craci_evidence, "fetch_live_evidence", lambda commit, token: unavailable)

    response = c.get("/.well-known/front-door-build.json")

    assert response.status_code == 200
    assert response.json() == unavailable
    assert response.headers["cache-control"] == "public, max-age=60"


def test_build_provenance_reads_configured_json_file(monkeypatch, tmp_path):
    provenance = {
        "commit": "abc123",
        "ci_run": "42",
        "craci_build_id": "801",
        "sbom_sha256": "deadbeef",
        "generated_at": "2026-11-14T12:34:56Z",
    }
    path = tmp_path / "build-provenance.json"
    path.write_text(json.dumps(provenance), encoding="utf-8")
    monkeypatch.setenv("BUILD_PROVENANCE_PATH", str(path))
    monkeypatch.setattr(signing.craci_evidence, "fetch_live_evidence",
                        lambda commit, token: {"status": "unavailable", "reason": "no_token"})

    assert c.get("/.well-known/front-door-build.json").json() == provenance
    assert signing.jwks()["keys"][0]["build"] == provenance


def test_invalid_build_provenance_uses_fallback(monkeypatch, tmp_path):
    path = tmp_path / "build-provenance.json"
    path.write_text("not json", encoding="utf-8")
    monkeypatch.setenv("BUILD_PROVENANCE_PATH", str(path))
    monkeypatch.setenv("RENDER_GIT_COMMIT", "fallback-commit")
    unavailable = {"commit": "fallback-commit", "status": "unavailable", "reason": "no_token"}
    monkeypatch.setattr(signing.craci_evidence, "fetch_live_evidence", lambda commit, token: unavailable)

    assert c.get("/.well-known/front-door-build.json").json() == unavailable
    assert signing.jwks()["keys"][0]["build"] == unavailable


def test_live_build_provenance_is_published_and_linked(monkeypatch):
    monkeypatch.delenv("BUILD_PROVENANCE_PATH", raising=False)
    monkeypatch.setenv("RENDER_GIT_COMMIT", "render-commit")
    monkeypatch.setenv("CRACI_API_TOKEN", "secret-token")
    live = {
        "commit": "render-commit", "ci_run": "42", "craci_job_ids": ["20"],
        "sbom_sha256": "deadbeef", "component_counts": {"pip": 1, "npm": 0},
        "direct_dependencies": [], "vulnerabilities": [], "blocking_vulnerabilities": [],
        "network_destinations": [], "fetched_at": "now", "source": "craci-api-live", "status": "ok",
    }
    monkeypatch.setattr(signing.craci_evidence, "fetch_live_evidence",
                        lambda commit, token: live if token == "secret-token" else {"status": "unavailable"})

    assert c.get("/.well-known/front-door-build.json").json() == live
    assert signing.jwks()["keys"][0]["build"] == live
