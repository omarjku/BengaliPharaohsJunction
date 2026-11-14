# Shared contracts v0.2

The message shapes the buyer's agent and Valio's front door agree on. Anyone (any language, any agent)
can code against the JSON Schemas in `schemas/`; Python code can import the Pydantic models.

| Shape | What it is |
|---|---|
| `PurchaseRequest` | What the buyer asked for, with the original words kept |
| `Mandate` | The buyer's rules: `hard_rules`, `uncertainty_policy`, `guidance`, `open_questions`, plus `blocklist`, `per_line_cap_cents`, `weekly_budget_cents`, `expires_at` |
| `Quote` | Valio's answer for one product: price, availability, known/unknown quantity, freshness, cut-off |
| `ProductFacts` | Static facts from the catalogue: names, category, allergens (CONTAINS / MAY_CONTAIN / FREE_FROM), reliability, minimum order, sales unit, pack size |
| `Decision` | `AUTO` / `ASK_HUMAN` / `DECLINE`, every reason (code, severity, text, facts, suggested fix), `primary_reason`, alternatives, `rules_version` |
| `AuditEntry` | One readable record: input, decision, and the options we rejected and why |

Rules built into the shapes:
- **Money is integer cents, net of VAT** (the customer price excluding VAT). Spend limits are compared on that net basis. `eur_to_cents()` converts the API's euro floats safely.
- Unknown fields are rejected, and every datetime carries a timezone.
- `Quote.quantity.known = false` means **unknown, not unlimited** (the mock API reports `999999`).
- The outcome is the highest reason severity (`DECLINE` > `ASK_HUMAN` > `INFO`, and `INFO` only means `AUTO`). `DECLINE` severity is allowed only for the codes in `HARD_CODES`; anything uncertain is `ASK_HUMAN`.
- Preferences carry a `scope`: `this_order` or `always`.

```bash
python -m venv .venv && .venv/Scripts/python -m pip install -e ".[dev]"   # Windows; use .venv/bin on macOS/Linux
python -m trade_contracts.export_schemas                                   # regenerate schemas/
python -m pytest
```

`examples/` holds one valid JSON per shape (the milk request; names and reliability in `ProductFacts.json` are illustrative).
Version: `contract_version` = `0.2` (breaking change from 0.1: cents, new reason codes and severity).
