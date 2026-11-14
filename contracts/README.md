# Shared contracts v0

The message shapes the buyer's agent and Valio's front door agree on. Anyone (any language, any agent)
can code against the JSON Schemas in `schemas/`; Python code can import the Pydantic models.

| Shape | What it is |
|---|---|
| `PurchaseRequest` | What the buyer asked for, with the original words kept |
| `Mandate` | The buyer's rules: `hard_rules`, `uncertainty_policy`, `guidance`, `open_questions` |
| `Quote` | Valio's answer for one product: price, availability, known/unknown quantity, freshness, cut-off |
| `Decision` | `AUTO` / `ASK_HUMAN` / `DECLINE`, reason codes, plain-language reasons, optional confidence, alternatives |
| `AuditEntry` | One readable record: input, decision, and the options we rejected and why |

Rules built into the shapes:
- Unknown fields are rejected, and every datetime carries a timezone.
- `Quote.quantity.known = false` means **unknown, not unlimited** (the mock API reports `999999`).
- Every `Decision` has at least one reason. `DECLINE` needs a hard-rule reason; anything uncertain is `ASK_HUMAN`.
- Preferences carry a `scope`: `this_order` or `always`.

```bash
python -m venv .venv && .venv/Scripts/python -m pip install -e ".[dev]"   # Windows; use .venv/bin on macOS/Linux
python -m trade_contracts.export_schemas                                   # regenerate schemas/
python -m pytest
```

`examples/` holds one valid JSON per shape (the milk request). Version: `contract_version` = `0.1`, expect changes.
