"""ProductFacts: static facts about a product (from the catalogue, T04), used by the
decision step (T06) for allergen, reliability and ordering-rule checks.

Order lines are resolved upstream (T05); this shape only describes the product."""

from __future__ import annotations

from pydantic import Field

from .common import AllergenStatus, VersionedModel


class ProductFacts(VersionedModel):
    product_id: str = Field(min_length=1)
    name_fi: str | None = None
    name_en: str | None = Field(default=None, description="A couple of products have no English name.")
    category: str | None = Field(default=None, description="null = not in the data (decision asks).")
    allergens: dict[str, AllergenStatus] = Field(
        default_factory=dict,
        description="Per allergen (lower-case name, e.g. 'gluten') CONTAINS / MAY_CONTAIN / "
        "FREE_FROM. An allergen that is absent means the data does not say.",
    )
    reliability: float | None = Field(
        default=None, ge=0, le=1, description="Delivery reliability 0-1; null = no record."
    )
    min_order_qty: float | None = Field(
        default=None, gt=0, description="Smallest order, in sales units; null = none stated."
    )
    sales_unit: str = Field(min_length=1, description="What one ordered unit is, e.g. '1 L carton'.")
    pack_size: float | None = Field(
        default=None, gt=0, description="Contents per sales unit, e.g. 12 for a 12 x 1 L case."
    )
