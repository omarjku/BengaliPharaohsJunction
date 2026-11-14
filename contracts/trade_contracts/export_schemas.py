"""Write the JSON Schemas to contracts/schemas/.

Run from the contracts/ folder:  python -m trade_contracts.export_schemas
"""

from __future__ import annotations

import json
from pathlib import Path

from . import SCHEMA_MODELS

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas"


def render(name: str) -> str:
    schema = SCHEMA_MODELS[name].model_json_schema()
    return json.dumps(schema, indent=2, ensure_ascii=False) + "\n"


def main() -> None:
    SCHEMA_DIR.mkdir(exist_ok=True)
    for name in SCHEMA_MODELS:
        (SCHEMA_DIR / f"{name}.schema.json").write_text(render(name), encoding="utf-8", newline="\n")
        print(f"wrote schemas/{name}.schema.json")


if __name__ == "__main__":
    main()
