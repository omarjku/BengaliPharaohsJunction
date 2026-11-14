r"""Record REAL Gemini answers as replay fixtures. The USER runs this in their own terminal:

    python compiler\tests\record_fixtures.py

It makes one LIVE Gemini call per sentence (6 calls) using GEMINI_API_KEY from the environment or
the repo's .env, asks for confirmation first, and overwrites the synthetic fixtures with real
answers (same keys, so the replay tests pick them up). It never prints the key: the only
key-related output is "GEMINI_API_KEY: present (length N)".

If a prompt (prompt.py), the schema (schema.py) or DEFAULT_MODELS changes, the keys change: record
again. Afterwards run:  python -m pytest compiler/tests -q
"""

from __future__ import annotations

import sys

from builders import FIXTURES, SENTENCES
from trade_contracts.common import PreferenceScope

from trade_compiler.llm import (
    DEFAULT_MODELS,
    GeminiLLM,
    LLMError,
    LLMMode,
    key_status,
    load_env_file,
)
from trade_compiler.prompt import build_prompt
from trade_compiler.schema import OUTPUT_SCHEMA

NAMES = ("allergens", "limit", "finnish", "ask", "ambiguous", "injection")


def main() -> int:
    load_env_file()
    status = key_status()
    print(status)
    if status.endswith("missing"):
        print("Put GEMINI_API_KEY=... in the repo's .env file, then run this again.")
        return 1
    print(f"Models (fallback order): {', '.join(DEFAULT_MODELS)}")
    print(f"This makes {len(NAMES)} LIVE Gemini calls and overwrites tests/fixtures/*.json.")
    if input("Type 'yes' to continue: ").strip().lower() != "yes":
        print("Cancelled; nothing was called.")
        return 1

    llm = GeminiLLM(LLMMode.RECORD, cache_dir=FIXTURES)
    failed = 0
    for name in NAMES:
        prompt = build_prompt(SENTENCES[name], PreferenceScope.ALWAYS)
        try:
            out = llm.generate_structured(prompt, OUTPUT_SCHEMA)
        except LLMError as exc:  # the wrapper never puts secrets or backend messages in here
            failed += 1
            print(f"  FAIL {name}: {exc}")
            continue
        filled = sorted(k for k, v in out.items() if v)
        print(f"  ok   {name}: filled {filled}")

    print(f"Done: {len(NAMES) - failed} recorded, {failed} failed.")
    if failed:
        print("A schema or model-name error here is expected to be small to fix; tell Claude the")
        print("FAIL lines above (they contain no secrets).")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
