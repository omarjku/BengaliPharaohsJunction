import pytest

from trade_contracts import SCHEMA_MODELS
from trade_contracts.export_schemas import SCHEMA_DIR, render


@pytest.mark.parametrize("name", sorted(SCHEMA_MODELS))
def test_committed_schema_matches_the_models(name):
    path = SCHEMA_DIR / f"{name}.schema.json"
    assert path.exists(), "run: python -m trade_contracts.export_schemas"
    assert path.read_text(encoding="utf-8") == render(name), (
        f"{name}.schema.json is stale; re-run: python -m trade_contracts.export_schemas"
    )
