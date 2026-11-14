"""Export the open contracts to docs/schemas/: the front door's OpenAPI 3.1 spec + one JSON Schema per contract.

Run from the repo root:  backend/.venv/bin/python docs/export_schemas.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.main import app  # noqa: E402  (importing doesn't start the server or load the catalogue)
from trade_contracts import SCHEMA_MODELS  # noqa: E402

OUT = ROOT / "docs" / "schemas"
OUT.mkdir(exist_ok=True)
docs = {"openapi": app.openapi()} | {name: model.model_json_schema() for name, model in SCHEMA_MODELS.items()}
for name, doc in docs.items():
    (OUT / f"{name}.json").write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote docs/schemas/{name}.json")
