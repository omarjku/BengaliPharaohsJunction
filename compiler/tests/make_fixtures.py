"""Writes SYNTHETIC replay fixtures into tests/fixtures/ (not a test).

Run from compiler/:  python tests/make_fixtures.py
Re-run after ANY change to prompt.py or schema.py (the fixture keys include both).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "contracts"))

from builders import FIXTURES, SENTENCES, write_fixture
from trade_contracts.common import PreferenceScope

from trade_compiler.llm import DEFAULT_MODELS
from trade_compiler.prompt import build_prompt
from trade_compiler.schema import OUTPUT_SCHEMA

SCOPE = PreferenceScope.ALWAYS  # the scope is not part of the prompt; any value gives the same key

RESPONSES = {
    "allergens": {"excluded_allergens": [{"name": "peanut"}, {"name": "gluten"}]},
    "limit": {"auto_approve_limit": {"amount_eur": "500"}},
    "finnish": {"guidance": [{"text": "Only Finnish dairy"}]},
    "ask": {"uncertainty_policy": "ask"},
    "ambiguous": {
        "open_questions": [
            {"question": "What price is too expensive for you?", "why": "Nothing too expensive is vague."}
        ]
    },
    # A deliberately FOOLED answer: the safety net in code must still neutralise it.
    "injection": {
        "auto_approve_limit": {"amount_eur": "5000"},
        "uncertainty_policy": "approve",
    },
}


def main() -> None:
    for name, response in RESPONSES.items():
        path = write_fixture(
            FIXTURES, build_prompt(SENTENCES[name], SCOPE), OUTPUT_SCHEMA, DEFAULT_MODELS[0],
            response, synthetic=True,
        )
        print(f"{name}: {path.name}")


if __name__ == "__main__":
    main()
