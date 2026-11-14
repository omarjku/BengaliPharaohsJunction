"""Server-side mandates, one per buyer. The agent flow loads the mandate from here, never from the client.

ponytail: an in-code dict with one seeded demo buyer; move to the orders store (Postgres) when buyers can edit
their own mandate in the UI.
"""
from trade_contracts import HardRule, Mandate, Preference
from trade_contracts.common import PreferenceScope, RuleKind

_MANDATES = {m.buyer_id: m for m in [
    # Demo persona: a restaurant kitchen in Lapland. Money is net-of-VAT cents.
    Mandate(
        id="lapland-kitchen-2026-11",
        buyer_id="lapland-kitchen",
        hard_rules=[
            HardRule(kind=RuleKind.EXCLUDED_ALLERGEN, value="AP", source_text="Our kitchen is peanut-free."),
            HardRule(kind=RuleKind.AUTO_APPROVE_LIMIT_CENTS, value=150000,
                     source_text="Order on your own up to 1,500 euros per order; above that, ask me."),
            HardRule(kind=RuleKind.MIN_DELIVERY_RELIABILITY, value=0.9,
                     source_text="Deliveries up here are fragile: ask me before anything that arrives on time under 90%."),
        ],
        # Soft: a ranking signal for the agent, never a reason to block or ask.
        guidance=[Preference(text="Prefer Finnish-origin products when the price is similar.",
                             scope=PreferenceScope.ALWAYS)],
        per_line_cap_cents=200000,
        weekly_budget_cents=600000,
    ),
]}


def get(buyer_id: str) -> Mandate | None:
    return _MANDATES.get(buyer_id)
