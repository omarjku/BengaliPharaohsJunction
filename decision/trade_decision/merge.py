"""Merge duplicate product lines before the stock and total checks (case 30)."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import replace

from .types import OrderLine


def valid_quantity(q: object) -> bool:
    """True for a finite, positive, real number (bool is not a quantity)."""
    return isinstance(q, int | float) and not isinstance(q, bool) and math.isfinite(q) and q > 0


def merge_lines(lines: Sequence[OrderLine]) -> tuple[OrderLine, ...]:
    """Combine lines for the same product_id (and same unit) by summing quantities.

    Order of first appearance is kept. A line whose quantity is not a valid positive number
    is NOT merged away: it stays as its own line so the quantity rule can reject it.
    Lines with different units for the same product stay separate (the unit rule reports it).
    """
    out: list[OrderLine] = []
    index: dict[tuple[str, str | None], int] = {}
    for line in lines:
        if not valid_quantity(line.quantity):
            out.append(line)
            continue
        key = (line.product_id, line.unit)
        if key not in index:
            index[key] = len(out)
            out.append(line)
            continue
        prev = out[index[key]]
        total = prev.quantity + line.quantity  # type: ignore[operator]
        if isinstance(total, float):
            total = round(total, 9)
        expected = prev.expected_unit_price_cents
        if expected is None:
            expected = line.expected_unit_price_cents
        out[index[key]] = replace(prev, quantity=total, expected_unit_price_cents=expected)
    return tuple(out)
