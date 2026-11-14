import json
from pathlib import Path

import jsonschema
import pytest

from trade_contracts import SCHEMA_MODELS

ROOT = Path(__file__).resolve().parent.parent
NAMES = sorted(SCHEMA_MODELS)


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", NAMES)
def test_example_validates_against_the_model(name):
    model = SCHEMA_MODELS[name].model_validate(load(ROOT / "examples" / f"{name}.json"))
    # dumping and re-reading must give the same object
    assert SCHEMA_MODELS[name].model_validate(model.model_dump(mode="json")) == model


@pytest.mark.parametrize("name", NAMES)
def test_example_validates_against_the_published_json_schema(name):
    schema = load(ROOT / "schemas" / f"{name}.schema.json")
    jsonschema.validate(load(ROOT / "examples" / f"{name}.json"), schema)


@pytest.mark.parametrize("name", NAMES)
def test_json_schema_rejects_an_unknown_field(name):
    schema = load(ROOT / "schemas" / f"{name}.schema.json")
    bad = {**load(ROOT / "examples" / f"{name}.json"), "surprise": 1}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)
