"""Alternatives (D21): offer up to 3 safe substitutes when a line cannot be ordered as asked."""

from __future__ import annotations

from zoneinfo import ZoneInfo

from trade_contracts import Alternative, ProductFacts
from trade_contracts.common import AllergenStatus, Availability

from .merge import valid_quantity
from .texts import eur
from .types import RuleContext

NO_SAFE_ALTERNATIVE = "No safe alternative found"


def is_local(facts: ProductFacts) -> bool:
    """Finnish origin. ProductFacts has no origin field yet (contract gap, see summary), so this
    reads `origin_country` if a later contract version adds it, and is False until then."""
    return getattr(facts, "origin_country", None) == "FI"


def _allergen_safe(ctx: RuleContext, facts: ProductFacts) -> bool:
    if ctx.mandate is None:
        return True
    for rule in ctx.mandate.hard_rules:
        if rule.kind.value != "excluded_allergen":
            continue
        name = str(rule.value).strip().lower()
        status = None
        for key, st in facts.allergens.items():
            if str(key).strip().lower() == name:
                status = st
        if status is not AllergenStatus.FREE_FROM:  # CONTAINS, MAY_CONTAIN and unknown all fail
            return False
    return True


def find_alternatives(ctx: RuleContext, product_id: str) -> list[Alternative]:
    """Alternatives for one ordered product, drawn from ctx.quotes / ctx.facts.

    Filter first (candidate must: not be the product itself, not blocklisted, be allergen-safe
    under the mandate, have a cut-off that has not passed, have enough KNOWN stock for the line's
    merged quantity), then rank by reliability, then Finnish origin, then price. Return at most
    ctx.config.max_alternatives (min 1 if any pass), labelled in `summary` as
    "Best match" / "Cheaper" / "Local" with the reason. Return [] when none pass; the caller then
    puts NO_SAFE_ALTERNATIVE into the reason's suggested_fix. Never invent products.
    """
    ordered = {ln.product_id for ln in ctx.lines}
    qty = 1.0
    for ln in ctx.lines:
        if ln.product_id == product_id and valid_quantity(ln.quantity):
            qty = float(ln.quantity)  # type: ignore[arg-type]
            break
    blocked = set(ctx.mandate.blocklist) if ctx.mandate else set()
    tz = ZoneInfo(ctx.config.timezone)
    now = ctx.now if ctx.now.tzinfo else ctx.now.replace(tzinfo=tz)

    candidates = []
    for pid in sorted(ctx.quotes):
        if pid in ordered or pid in blocked:
            continue
        quote = ctx.quotes[pid]
        facts = ctx.facts.get(pid)
        if facts is None:
            continue
        if quote.availability is Availability.UNAVAILABLE:
            continue
        if quote.unit_price_cents is None or quote.unit_price_cents <= 0:
            continue
        if not _allergen_safe(ctx, facts):
            continue
        if quote.cut_off is not None and now >= quote.cut_off.closing_time:
            continue
        info = quote.quantity
        if (
            not info.known
            or info.value is None
            or info.value >= ctx.config.qty_unknown_threshold
            or info.value < qty
        ):
            continue
        candidates.append((pid, quote, facts))

    def rank(item):
        pid, quote, facts = item
        rel = facts.reliability if facts.reliability is not None else -1.0
        return (-rel, 0 if is_local(facts) else 1, quote.unit_price_cents, pid)

    candidates.sort(key=rank)
    chosen = candidates[: ctx.config.max_alternatives]
    out: list[Alternative] = []
    for i, (pid, quote, facts) in enumerate(chosen):
        name = facts.name_en or quote.product_name or facts.name_fi or pid
        price = eur(quote.unit_price_cents)
        if i == 0:
            label = "Best match"
            why = (
                f"reliability {facts.reliability:.0%}"
                if facts.reliability is not None
                else "no delivery record"
            )
        elif is_local(facts):
            label, why = "Local", "Finnish origin"
        else:
            best_price = chosen[0][1].unit_price_cents
            label = "Cheaper" if quote.unit_price_cents < best_price else "Alternative"
            why = f"{eur(best_price - quote.unit_price_cents)} less per unit than the best match" if (
                quote.unit_price_cents < best_price
            ) else "safe and in stock"
        out.append(Alternative(product_id=pid, summary=f"{label}: {name}, {price} per unit ({why})"))
    return out
