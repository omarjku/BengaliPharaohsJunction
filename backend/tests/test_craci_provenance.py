import json

from fastapi.testclient import TestClient

from app import signing
from app.main import app


c = TestClient(app)


def test_build_provenance_has_safe_fallback(monkeypatch):
    monkeypatch.delenv("BUILD_PROVENANCE_PATH", raising=False)
    monkeypatch.setenv("RENDER_GIT_COMMIT", "render-commit")

    response = c.get("/.well-known/front-door-build.json")

    assert response.status_code == 200
    assert response.json() == {"commit": "render-commit", "sbom": "unavailable"}
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

    assert c.get("/.well-known/front-door-build.json").json() == provenance
    assert signing.jwks()["keys"][0]["build"] == provenance


def test_invalid_build_provenance_uses_fallback(monkeypatch, tmp_path):
    path = tmp_path / "build-provenance.json"
    path.write_text("not json", encoding="utf-8")
    monkeypatch.setenv("BUILD_PROVENANCE_PATH", str(path))
    monkeypatch.setenv("RENDER_GIT_COMMIT", "fallback-commit")

    assert c.get("/.well-known/front-door-build.json").json() == {
        "commit": "fallback-commit",
        "sbom": "unavailable",
    }
    assert "build" not in signing.jwks()["keys"][0]
