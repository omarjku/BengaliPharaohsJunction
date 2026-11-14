"""T05 quantity resolver: a buyer's amount ("1,000 L", "40 kg", "12 pcs", "3 KI") → sales units to order.

Never guesses. If the catalogue data can't support the conversion, quantity is None and needs_confirmation
is True; if the conversion rests on an assumption, the answer is given but needs_confirmation is still True.
Exact arithmetic with Fraction (no float drift); numbers are rounded to 3 decimals only on output.

Data facts this relies on (checked against the full catalogue, Sat 14 Nov):
- volume / net_weight are per BASE unit, in LTR/CLT/MLT or KGM/GRM. "volume" is often a weight (GRM/KGM)
  or a piece count (H87) for solids, so it is only used when its unit really is a volume.
- When the sales unit is a case (KI = n base units), the "per base unit" measure is sometimes the whole case
  (e.g. 476731 Valio butter 5 kg: KI = 4 ST but net_weight 20 kg), so case conversions are always flagged.
- Base unit KG means 1 base unit = 1 kg; for those, net_weight is the approximate piece weight, not 1 kg,
  and a case of them (KI = n KG) is only approximately n kg.
- allowedLotSize: the order quantity (in sales units) must be a multiple of it. 0.01 = no real constraint.
- Names like "Happy Chef 40x180g" with a measure of 180 g mean the measure is ONE inner item; if the units
  table doesn't say a KI is 40 base units, the base unit may be the whole case, so those are flagged.
"""
import math
import re
from fractions import Fraction

# requested unit → (dimension, size in L / kg / base units)
MEASURES = {
    "l": ("volume", Fraction(1)), "dl": ("volume", Fraction(1, 10)), "cl": ("volume", Fraction(1, 100)),
    "ml": ("volume", Fraction(1, 1000)), "kg": ("weight", Fraction(1)), "g": ("weight", Fraction(1, 1000)),
    "pcs": ("count", Fraction(1)), "units": ("count", Fraction(1)),
}
# Valio data unit → (dimension, size in L / kg). Anything else (H87 pieces, PTN, MTR, PR...) is unusable.
DATA_UNITS = {"LTR": ("volume", Fraction(1)), "CLT": ("volume", Fraction(1, 100)), "MLT": ("volume", Fraction(1, 1000)),
              "KGM": ("weight", Fraction(1)), "GRM": ("weight", Fraction(1, 1000))}
FIELD = {"volume": "volume", "weight": "net_weight"}
PACK = re.compile(r"(\d+)\s*[x×]\s*(\d+(?:[.,]\d+)?)\s*(kg|g|l|dl|cl|ml)\b", re.I)  # "40x180g", "5 x 2,5 kg"


def _q(x) -> Fraction:
    return Fraction(str(x))  # via str: 0.1 stays 1/10, not the binary float


def _num(x: Fraction) -> int | float:
    return int(x) if x.denominator == 1 else float(f"{float(x):.12g}")  # significant figures: 1/2280 stays > 0


def _fmt(x: Fraction) -> str:
    return f"{float(x):,.3f}".rstrip("0").rstrip(".") if abs(x) >= 1 or x == 0 else f"{float(x):.3g}"


def _pack_note(product: dict, dim: str, per_base: Fraction) -> str | None:
    """Flag "N x size" names whose size is the recorded per-base measure while nothing says a KI is N base units."""
    m = PACK.search(product.get("name_en") or "")
    if not m or int(m[1]) < 2 or _q(product["units"].get("KI") or 0) == int(m[1]):
        return None
    name_dim, size = MEASURES[m[3].lower()]
    if name_dim != dim or abs(_q(m[2].replace(",", ".")) * size / per_base - 1) > Fraction(1, 20):
        return None
    base = product["base_unit"]
    return (f"assumes one {base} holds {_fmt(per_base)} {'L' if dim == 'volume' else 'kg'} as recorded, but the name says "
            f"{m[0]}, so one {base} may be the whole case of {m[1]}")


def _per_sales_unit(product: dict, unit: str) -> tuple[Fraction | None, str | None, str]:
    """How many requested units one sales unit holds, any assumption made, and how it was derived."""
    sales, base, units = product["sales_unit"], product["base_unit"], product["units"]
    base_per_sales = _q(units.get(sales) or 0)
    if base_per_sales <= 0:
        return None, None, f"the size of one {sales} in base units is missing"
    case = f" × {_fmt(base_per_sales)} {base} per {sales}" if sales != base else ""
    dim, size = MEASURES.get(unit.lower(), (None, None))

    if dim in ("volume", "weight"):
        assumption = None
        if dim == "weight" and base == "KG":
            per_base, how = Fraction(1), "1 kg per KG"
            if sales != base:  # e.g. 464997 "6x ... appr 2 kg" but KI = 6 KG: case weights are approximate
                assumption = f"assumes one {sales} weighs {_fmt(base_per_sales)} kg as listed (case weights are approximate)"
        else:
            m = product.get(FIELD[dim])
            if not m:
                return None, None, f"no {dim} is recorded for this product"
            data_dim, data_size = DATA_UNITS.get(m.get("unit"), (None, None))
            if data_dim != dim:
                return None, None, f"its {dim} is recorded in {m.get('unit')}, which is not a {dim} unit"
            per_base = _q(m.get("value") or 0) * data_size
            if per_base <= 0:
                return None, None, f"its recorded {dim} is zero"
            how = f"{_fmt(m['value'])} {m['unit']} per {base}"
            notes = [_pack_note(product, dim, per_base)]
            if sales != base:
                notes.append(f"assumes the recorded {dim} is per {base}, not per whole {sales} "
                             "(Valio's data sometimes gives the whole case)")
            assumption = "; ".join(n for n in notes if n) or None
        return per_base * base_per_sales / size, assumption, how + case

    if dim == "count":
        if base == "KG":
            return None, None, "it is sold by weight (KG), not by the piece"
        assumption = None if base == "ST" else f"assumes one piece = one {base}"
        return base_per_sales, assumption, f"1 piece = 1 {base}" + case

    code = unit.upper()
    if code in units and _q(units[code]) > 0:
        how = "ordered directly" if code == sales else f"1 {code} = {_fmt(_q(units[code]))} {base}{case}"
        assumption = (f"assumes one {code} weighs {_fmt(_q(units[code]))} kg as listed (piece weights are approximate)"
                      if base == "KG" and code != sales else None)
        return base_per_sales / _q(units[code]), assumption, how
    return None, None, f"'{unit}' is not a unit of this product (it has: {', '.join(units)})"


def resolve(product: dict, amount: float, unit: str) -> dict:
    """Sales units to order for `amount` `unit` of `product` (a catalogue dict), rounded UP to a whole sales
    unit (KG sales units stay continuous) and to the lot size. Pure function."""
    sales = product["sales_unit"]
    want = _q(amount)
    per_sales, assumption, how = _per_sales_unit(product, unit)
    out = {"product_id": product["id"], "requested": {"amount": _num(want), "unit": unit}, "sales_unit": sales,
           "quantity": None, "per_sales_unit": None, "delivered": None, "over_delivery": None, "rounded_up": False}
    if per_sales is None:
        return out | {"confidence": "none", "needs_confirmation": True,
                      "explanation": f"Can't convert {_fmt(want)} {unit} into {sales}: {how}. Please confirm the quantity in {sales}."}

    lot = _q(product.get("lot_size") or 0)
    if lot <= 0:
        return out | {"confidence": "none", "needs_confirmation": True,
                      "explanation": f"Can't round {_fmt(want)} {unit} to an orderable amount: the lot size is missing. Please confirm the quantity in {sales}."}
    if lot != Fraction(1, 100) and sales != product["base_unit"]:  # e.g. 464997: lot 2 with KI = 6 KG; 2 KI or 2 KG?
        note = f"assumes the lot size {_fmt(lot)} is in {sales}, not {product['base_unit']}"
        assumption = f"{assumption}; {note}" if assumption else note
    step = lot if sales == "KG" else Fraction(lot.numerator)  # smallest whole number of sales units that is a lot multiple
    need = want / per_sales
    qty = math.ceil(need / step) * step
    delivered = qty * per_sales
    text = f"{_fmt(want)} {unit} ÷ {_fmt(per_sales)} {unit} per {sales} ({how}) = {_fmt(need)} {sales}."
    if qty != need:
        why = f"lot size {_fmt(lot)}" if step != 1 else "whole units"
        text += f" Rounded up to {_fmt(qty)} {sales} ({why}): delivers {_fmt(delivered)} {unit}, {_fmt(delivered - want)} {unit} more than asked."
    if assumption:
        text += f" Please confirm: {assumption}."
    return out | {"quantity": _num(qty), "per_sales_unit": _num(per_sales), "delivered": _num(delivered),
                  "over_delivery": _num(delivered - want), "rounded_up": qty != need,
                  "confidence": "medium" if assumption else "high", "needs_confirmation": bool(assumption),
                  "explanation": text}
