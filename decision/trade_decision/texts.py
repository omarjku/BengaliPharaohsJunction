"""Chef-facing reason templates (section B of the T06 doc). Text is separate from the code.

TEMPLATES maps a ReasonCode to (message, suggested_fix). Placeholders are filled from the
reason's `facts`; money facts are net cents and are shown with `eur()`.
"""

from __future__ import annotations

from collections.abc import Mapping

from trade_contracts import ReasonCode

TEMPLATES: dict[ReasonCode, tuple[str, str | None]] = {
    ReasonCode.QTY_INVALID: (
        "Quantity must be a positive number. How much do you need?",
        "Tell me how much you need.",
    ),
    ReasonCode.QTY_SUSPICIOUS: (
        "{quantity} of {product} looks like a typo, so I won't order it.",
        "Check the quantity and confirm it.",
    ),
    ReasonCode.QTY_AMBIGUOUS: (
        "Minimum order for {product} is {min_order_qty}; you asked for {quantity}.",
        "Raise the quantity to the minimum or pick another product.",
    ),
    ReasonCode.QTY_UNKNOWN: (
        (
            "Valio has not told us how much of {product} is available (the system shows a "
            "placeholder, not a real stock figure). I won't guess."
        ),
        "Ask Valio, or pick an alternative with a confirmed quantity.",
    ),
    ReasonCode.STOCK_PARTIAL: (
        "Only {available} of your {requested} {product} are in stock ({coverage_pct}%).",
        "Take {available} now, take {available} plus a substitute for the rest, or wait.",
    ),
    ReasonCode.STOCK_NONE: (
        "{product} is out of stock.",
        "Pick an alternative or wait for stock.",
    ),
    ReasonCode.UNIT_MISMATCH: (
        "Unit mismatch: you asked in {requested_unit} but {product} is sold as {sales_unit}.",
        "Say how much you need in {sales_unit}, or pick a product sold in {requested_unit}.",
    ),
    ReasonCode.CUTOFF_PASSED: (
        "Ordering for {product} closed {closing}.",
        "Want an alternative that can still arrive in time?",
    ),
    ReasonCode.UNDELIVERABLE: (
        "{product} can't be delivered to you right now and no quantity is confirmed.",
        "Pick an alternative or ask Valio.",
    ),
    ReasonCode.DATE_NOT_HONOURED: (
        "Valio's delivery date for {product} is {available_date}; you asked for {needed_by}.",
        "Accept the new date, or pick an alternative that arrives by {needed_by}.",
    ),
    ReasonCode.LOW_RELIABILITY: (
        "{detail}",
        "Approve anyway, or pick a more reliable product.",
    ),
    ReasonCode.QUOTE_STALE: (
        "The stock and price data for {product} is old ({age_minutes} minutes).",
        "Fetch a fresh quote and check again.",
    ),
    ReasonCode.PRICE_MISSING: (
        "There is no usable price for {product}, so I can't cost this order.",
        "Ask Valio for a price or pick another product.",
    ),
    ReasonCode.PRICE_CHANGED: (
        "Price of {product} changed from {expected} to {price} per unit ({change_pct}%).",
        "Approve the new price or decline.",
    ),
    ReasonCode.UNKNOWN_PRODUCT: (
        "Product {product_id} was not found, so it was not ordered.",
        "Check the product, or choose an alternative.",
    ),
    ReasonCode.DATA_MISSING: (
        "We have no {missing} for {product}, so I can't check it.",
        "Ask Valio for the missing data or pick another product.",
    ),
    ReasonCode.SPEND_OVER_LIMIT: (
        "This order is {total} (net of VAT), above your {limit} auto-approve limit.",
        "Approve, reduce the quantity to fit the limit, or decline.",
    ),
    ReasonCode.LINE_OVER_CAP: (
        "{product} costs {line_total} (net of VAT), above your {cap} per-line cap.",
        "Approve, reduce the quantity, or decline.",
    ),
    ReasonCode.WEEKLY_BUDGET_EXCEEDED: (
        "This would take your 7-day spend to {projected} (net of VAT); your weekly budget is {budget}.",
        "Approve, reduce the quantity, or wait for budget to free up.",
    ),
    ReasonCode.ALLERGEN_CONTAINS: (
        "Not ordered: {product} contains {allergen} and your mandate excludes it.",
        "Choose an {allergen}-free product, or change the mandate.",
    ),
    ReasonCode.ALLERGEN_MAY_CONTAIN: (
        "{product} may contain traces of {allergen}; the supplier cannot rule it out.",
        "Okay for this order, or pick an alternative?",
    ),
    ReasonCode.ALLERGEN_DATA_MISSING: (
        "We can't confirm whether {product} contains {allergen}; the data does not say.",
        "Ask Valio, or pick a product with confirmed allergen data.",
    ),
    ReasonCode.POLICY_DECLINE_UNKNOWN: (
        "Not ordered: we can't confirm {allergen} for {product}, and your policy says decline on unknown.",
        "Pick a product with confirmed allergen data, or change the policy.",
    ),
    ReasonCode.BLOCKLISTED: (
        "Not ordered: {product} is on your blocked list.",
        "Pick another product, or remove it from the blocked list.",
    ),
    ReasonCode.MANDATE_MISSING: (
        "No buying rules (mandate) are on file for you, so a person must check this order.",
        "Set up a mandate, or approve this order by hand.",
    ),
    ReasonCode.MANDATE_EXPIRED: (
        "Your buying rules (mandate) expired {expired_at}, so a person must check this order.",
        "Renew the mandate, or approve this order by hand.",
    ),
    ReasonCode.MANDATE_INVALID: (
        "{detail}",
        "Fix the rule in the mandate, or approve this order by hand.",
    ),
    ReasonCode.DEFAULT_MANDATE_APPLIED: (
        "You have no buying rules set, so standard defaults were used (limit {limit}).",
        None,
    ),
    ReasonCode.LIMIT_CHANGE_ATTEMPT: (
        "Not ordered: the request tried to change spending limits or rules. Only a human can change limits.",
        "Change the mandate yourself if you want different limits.",
    ),
    ReasonCode.LOW_CONFIDENCE: (
        "I'm not confident I understood this request correctly (confidence {confidence}).",
        "Check the order and approve it, or correct it.",
    ),
    ReasonCode.ENGINE_ERROR: (
        "The check failed, so this order is held for a human.",
        "Ask a person to review it.",
    ),
}


def eur(cents: int) -> str:
    """Integer cents -> 'EUR 1,400.00'."""
    sign = "-" if cents < 0 else ""
    whole, frac = divmod(abs(int(cents)), 100)
    return f"{sign}EUR {whole:,}.{frac:02d}"


class _Safe(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def render(code: ReasonCode, facts: Mapping[str, object] | None = None) -> tuple[str, str | None]:
    """(message, suggested_fix) for a code. Money placeholders `total`, `limit`, ... may be
    given as `<name>_cents` facts and are formatted with eur(). Never raises."""
    message, fix = TEMPLATES.get(code, (code.value.replace("_", " ").capitalize() + ".", None))
    values = _Safe(facts or {})
    for key, value in list(values.items()):
        if key.endswith("_cents") and isinstance(value, int) and not isinstance(value, bool):
            values[key.removesuffix("_cents")] = eur(value)
    try:
        return message.format_map(values), (fix.format_map(values) if fix else None)
    except (ValueError, IndexError, AttributeError):
        return message, fix
