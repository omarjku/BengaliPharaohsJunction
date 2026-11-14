"""Money helper for the boundary with the Valio API, which returns euro floats.

Everything inside the contracts is integer cents, net of VAT (customer price excluding VAT).
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation


def eur_to_cents(value: float | str | Decimal) -> int:
    """Convert euros to integer cents, rounding half up, without float error
    (1.15 * 100 is 114.99999... as a float)."""
    try:
        cents = (Decimal(str(value)) * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"not a valid euro amount: {value!r}") from exc
    if not cents.is_finite():
        raise ValueError(f"not a valid euro amount: {value!r}")
    return int(cents)
