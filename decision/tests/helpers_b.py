"""Extra helpers for the rule tests (kept apart from builders.py)."""

from __future__ import annotations

from builders import codes, make_facts, make_line, make_quote, run
from trade_contracts import Decision, Reason

ASK = "ASK_HUMAN"
AUTO = "AUTO"
DECLINE = "DECLINE"


def check(d: Decision, outcome: str, *expected: str) -> None:
    """Outcome matches and every expected reason code is present."""
    assert d.outcome.value == outcome, f"{d.outcome} {codes(d)}"
    for code in expected:
        assert code in codes(d), f"{code} missing from {codes(d)}"


def reason(d: Decision, code: str) -> Reason:
    found = [r for r in d.reasons if r.code.value == code]
    assert found, f"{code} missing from {codes(d)}"
    return found[0]


def candidate(pid: str, price: int = 140, stock: int | None = 5000, reliability: float = 0.95,
              allergens: dict | None = None, **quote_kw):
    """A (quote, facts) pair for an alternative candidate; clean by default."""
    q = make_quote(pid, price_cents=price, stock=stock, **quote_kw)
    f_kw: dict = {"reliability": reliability}
    if allergens is not None:
        f_kw["allergens"] = allergens
    return q, make_facts(pid, **f_kw)


def order_with(candidates=(), line=None, order_quote=None, order_facts=None, **kw) -> Decision:
    """Run one ordered line (clean by default) plus alternative candidates in the pool."""
    line = line or make_line()
    quotes = [order_quote or make_quote(line.product_id), *[c[0] for c in candidates]]
    facts = [order_facts or make_facts(line.product_id), *[c[1] for c in candidates]]
    return run(lines=[line], quotes=quotes, facts=facts, **kw)
