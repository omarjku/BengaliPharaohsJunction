from decimal import Decimal

import pytest

from trade_contracts import eur_to_cents


@pytest.mark.parametrize(
    ("euros", "cents"),
    [
        (1.4, 140),
        (1.15, 115),  # float 1.15 * 100 would be 114.99999...
        (31.31, 3131),
        (0, 0),
        ("12.345", 1235),  # half up
        (0.005, 1),
        (Decimal("2.50"), 250),
        (-1.4, -140),
    ],
)
def test_eur_to_cents(euros, cents):
    assert eur_to_cents(euros) == cents


@pytest.mark.parametrize("bad", ["abc", "nan", float("nan"), float("inf"), None])
def test_eur_to_cents_rejects_non_numbers(bad):
    with pytest.raises(ValueError):
        eur_to_cents(bad)
