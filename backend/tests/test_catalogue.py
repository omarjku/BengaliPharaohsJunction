"""Catalogue: slimming the raw product shape, search filters, and the loading guard. No real data needed."""
import pytest
from fastapi.testclient import TestClient

from app import catalogue

RAW = {
    "id": "463335", "salesUnit": "ST", "baseUnit": "ST", "category": "C1", "allowedLotSize": 0.01, "deleted": False,
    "vendorName": "VALIO OY", "countryOfOrigin": "fi", "temperatureCondition": 2,
    "units": [{"unitId": "ST", "sizeInBaseUnits": 1.0}, {"unitId": "KI", "sizeInBaseUnits": 5.0}],
    "deposits": [{"material": "4", "unit": "ST", "quantity": 5.0}],
    "substitutions": [{"product": "463335", "substituteProduct": "476240"}],
    "synkkaData": {
        "names": [{"language": "en", "value": "Valio Eila 3 % milk drink 1 l lactose free"},
                  {"language": "fi", "value": "Valio Eila 3 % maitojuoma 1 l laktoositon"}],
        "brand": "Valio",
        "classifications": [
            {"name": "allergen", "type": "ENUM", "values": [{"id": "AM", "unit": "CONTAINS"}, {"id": "AN", "unit": "MAY_CONTAIN"}, {"id": "AP", "unit": "UNDECLARED"}]},
            {"name": "nonAllergen", "type": "ENUM", "values": [{"id": "AE", "unit": "FREE_FROM"}]},
            {"name": "nutritionalClaim", "type": "ENUM", "values": [{"id": "FREE_FROM_LACTOSE"}]},
        ],
        "unitConversions": [{"synkkaPackagingType": "BASE_UNIT_OR_EACH", "volume": {"unit": "LTR", "value": 1.0},
                             "netWeight": {"unit": "GRM", "value": 1025.0}}],
        "vatCode": "MEDIUM",
    },
}


@pytest.fixture
def loaded(monkeypatch):
    slim = catalogue._slim(RAW)
    other = dict(slim, id="1", name_en="Wheat pasta 500 g", name_fi="Vehnäpasta", claims=[],
                 allergens={"contains": ["AW"], "may_contain": [], "free_from": []})
    monkeypatch.setattr(catalogue, "_products", {"463335": slim, "1": other})
    monkeypatch.setattr(catalogue, "_ready", type("E", (), {"is_set": lambda self: True})())
    return slim


def test_slim_extracts_claims_allergens_units_and_volume(loaded):
    assert loaded["claims"] == ["FREE_FROM_LACTOSE"]
    assert loaded["allergens"] == {"contains": ["AM"], "may_contain": ["AN"], "free_from": ["AE"], "undeclared": ["AP"]}
    assert loaded["units"] == {"ST": 1.0, "KI": 5.0} and loaded["volume"] == {"unit": "LTR", "value": 1.0}
    assert loaded["substitutes"] == ["476240"] and loaded["name_fi"].endswith("laktoositon")
    assert loaded["deposits"] == [{"material": "4", "unit": "ST", "quantity": 5.0}]


def test_load_rebuilds_slim_when_version_is_stale(monkeypatch, tmp_path):
    import json
    import threading

    slim_path = tmp_path / "catalogue_slim.json"
    slim_path.write_text('{"version": "old", "products": [{"id": "stale"}]}')
    rebuilt = []

    def rebuild():
        rebuilt.append(True)
        slim_path.write_text(json.dumps({"version": catalogue.SLIM_VERSION, "products": [{"id": "fresh"}]}))

    monkeypatch.setattr(catalogue, "SLIM", slim_path)
    monkeypatch.setattr(catalogue, "build_slim", rebuild)
    monkeypatch.setattr(catalogue, "_products", {})
    monkeypatch.setattr(catalogue, "_ready", threading.Event())

    catalogue.load()

    assert rebuilt == [True] and set(catalogue._products) == {"fresh"}


def test_search_filters(loaded):
    assert [p["id"] for p in catalogue.search("milk", claims=["FREE_FROM_LACTOSE"])] == ["463335"]
    assert [p["id"] for p in catalogue.search("maitojuoma")] == ["463335"]              # Finnish name
    assert catalogue.search("milk", exclude_allergens=["AM"]) == []                       # milk allergy excludes it
    assert catalogue.search("milk", exclude_allergens=["AN"])                              # MAY_CONTAIN ok by default
    assert catalogue.search("milk", exclude_allergens=["AN"], strict_may_contain=True) == []
    assert catalogue.search("pasta milk") == []                                           # every term must match


def test_routes_answer_503_until_loaded_then_200(monkeypatch, loaded):
    from app.main import app
    c = TestClient(app)
    assert c.get("/api/products/search", params={"q": "milk", "claims": "FREE_FROM_LACTOSE"}).json()[0]["id"] == "463335"
    assert c.get("/api/products/463335").status_code == 200 and c.get("/api/products/999").status_code == 404
    assert c.get("/api/products/search", params={"claims": "bad code!"}).status_code == 422
    monkeypatch.setattr(catalogue, "_ready", type("E", (), {"is_set": lambda self: False})())
    assert c.get("/api/products/search", params={"q": "milk"}).status_code == 503
