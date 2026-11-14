"""Conversational follow-ups: the chef's spoken or typed ANSWER to the agent's question continues the same request.

When /api/agent/ask asks for one thing it can continue from (the amount of an item, the delivery day, the number of
guests, or "order again?"), it stores the original request for FOLLOW_UP_TTL_S, per buyer, under DATA_DIR, and
returns a conversation_id. The answer may fill ONLY the field that was asked: it is parsed deterministically
(numbers in words too, English and Finnish), and everything else, the buyer, the limits and the other items, comes
from the stored request and the server-side mandate. The request then re-runs through every check.
Also here: speak(), the one-sentence spoken version of any /ask response.
"""
import json
import hashlib
import os
import re
import threading
import time
from datetime import date, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from . import config, quantity

STORE = config.DATA_DIR / "conversations.json"
_DEFAULT_STORE = STORE
FOLLOW_UP_TTL_S = 600
MAX_OPEN = 2000
_lock = threading.Lock()

# Spoken numbers → digits (voice transcripts write "Sata litraa", "two hundred and fifty"). English as phrases,
# Finnish as the compound words it writes ("sataviisikymmentä" = 150), plus halves ("kaksi ja puoli", "one and a half").
_EN = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
       "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
       "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
       "seventy": 70, "eighty": 80, "ninety": 90}
_FI = {"yksi": 1, "yhden": 1, "kaksi": 2, "kahden": 2, "kolme": 3, "neljä": 4, "viisi": 5, "kuusi": 6,
       "seitsemän": 7, "kahdeksan": 8, "yhdeksän": 9}


_DOZEN = ("dozen", "tusina", "tusinaa")
HELSINKI = ZoneInfo("Europe/Helsinki")


def _fi(w: str) -> int | None:
    """One Finnish number word: 'kaksisataaviisikymmentä' → 250, 'tuhat' → 1000; None if it isn't one."""
    for one, many, mult in (("tuhat", "tuhatta", 1000), ("sata", "sataa", 100)):
        for form in (many, one):  # "sataa" before "sata"
            if (i := w.find(form)) < 0 or (form == one) != (i == 0):  # "sata" alone, "kaksisataa" with a multiplier
                continue
            left = _fi(w[:i]) if i else 1
            right = _fi(w[i + len(form):]) if w[i + len(form):] else 0
            if left is None or right is None or right >= mult or (form == many and left < 2):
                return None
            return left * mult + right
    if w == "kymmenen":
        return 10
    if m := re.fullmatch(r"(.+?)toista", w):
        return 10 + u if (u := _FI.get(m[1])) else None
    if m := re.fullmatch(r"(.+?)kymmentä(.*)", w):
        tens, unit = _FI.get(m[1]), _FI.get(m[2]) if m[2] else 0
        return tens * 10 + unit if tens and tens > 1 and unit is not None else None
    return _FI.get(w)


def _fmt(n: float) -> str:
    return str(int(n)) if n == int(n) else f"{n:g}"


def spoken_to_digits(text: str) -> str:
    """'Sata litraa' → '100 litraa', 'two hundred and fifty kg' → '250 kg', 'kaksi ja puoli' → '2.5'. Digits and
    every other word stay as they are. 'a'/'and'/'ja' join numbers only inside a number phrase."""
    toks = re.findall(r"[\wäöåÄÖÅ]+|[^\wäöåÄÖÅ]+", text)
    out, i = [], 0
    while i < len(toks):
        low = toks[i].lower()
        if low.isspace():  # a number phrase starts on a word, never on the space before it
            out.append(toks[i]); i += 1; continue
        if low in ("puoli", "half"):  # "half a kilo" → "0.5 kilo"
            skip = 3 if low == "half" and i + 2 < len(toks) and toks[i + 2].lower() == "a" else 1
            out.append("0.5"); i += skip; continue
        if low == "puolitoista":
            out.append("1.5"); i += 1; continue
        if low in ("a", "an") and i + 2 < len(toks) and toks[i + 1].isspace() and toks[i + 2].lower() in UNIT_WORDS:
            out.append("1"); i += 1; continue  # "a kilo of butter" → "1 kilo"; "a litre" → "1 litre"
        total = cur = None
        j, last = i, i - 1
        while j < len(toks):
            w = toks[j].lower()
            nxt = toks[j + 2].lower() if j + 2 < len(toks) and not toks[j + 1].strip() else None
            if w.isspace():
                j += 1; continue
            if (v := _EN.get(w, _fi(w))) is not None:  # "twenty five" → 25
                cur = (cur or 0) + v
            elif w in ("hundred", "thousand", *_DOZEN) or (w in ("a", "an") and nxt in ("hundred", "thousand", *_DOZEN) and cur is None
                                 and total is None):
                if w in ("a", "an"):
                    cur = 1
                elif w in _DOZEN:  # "a dozen" 12, "two dozen" 24, "tusina" 12, "kaksi tusinaa" 24
                    cur = (cur or 1) * 12
                elif w == "hundred":
                    if cur is None and total is None:
                        break
                    cur = (cur or 1) * 100
                else:
                    if cur is None and total is None:
                        break
                    total, cur = (total or 0) + (cur or 1) * 1000, None
            elif w in ("and", "ja") and (cur is not None or total is not None) and nxt is not None:
                after = toks[j + 4].lower() if j + 4 < len(toks) else None
                if nxt in ("puoli",) or (nxt == "a" and after == "half"):  # "kaksi ja puoli", "one and a half"
                    value = (total or 0) + (cur or 0) + 0.5
                    last = j + (2 if nxt == "puoli" else 4)
                    total, cur = value, None
                    j = last + 1
                    break
                if nxt in _EN and w == "and":  # "two hundred and fifty"
                    j += 1; continue
                break
            else:
                break
            last = j
            j += 1
        if last >= i:
            out.append(_fmt((total or 0) + (cur or 0)))
            i = last + 1
        else:
            out.append(toks[i]); i += 1
    return "".join(out)


UNIT_WORDS = {"l": "L", "litre": "L", "litres": "L", "liter": "L", "liters": "L", "litra": "L", "litraa": "L",
              "dl": "dl", "desi": "dl", "kg": "kg", "kilo": "kg", "kilos": "kg", "kiloa": "kg", "kilograms": "kg",
              "g": "g", "gram": "g", "grams": "g", "grammaa": "g", "pcs": "pcs", "pieces": "pcs", "piece": "pcs",
              "kpl": "pcs", "kappaletta": "pcs"}
YES = re.compile(r"^\s*(yes|yeah|yep|sure|ok|okay|again|order again|kyllä|joo|juu|tilaa)\b", re.I)
NO = re.compile(r"^\s*(no|nope|cancel|don'?t|ei|älä|peru)\b", re.I)


def number_in(answer: str) -> float | None:
    """'5', '1,5', 'five', 'kaksikymmentä', 'sataviisikymmentä' → the number; None if the answer has none."""
    m = re.search(r"\d+(?:[.,]\d+)?", spoken_to_digits(answer))
    return float(m[0].replace(",", ".")) if m else None


def amount_in(answer: str, default_unit: str | None = None) -> tuple[float, str] | None:
    """'five litres' → (5.0, 'L'); a bare number takes the unit the question implied (if any)."""
    n = number_in(answer)
    unit = next((u for w, u in UNIT_WORDS.items() if re.search(rf"(?<![a-zäö]){re.escape(w)}(?![a-zäö])", answer.lower())),
                default_unit)
    if n is None or not unit or not 0 < n <= 1_000_000 or unit.lower() not in quantity.MEASURES:
        return None
    return n, unit


def language(text: str) -> str:
    if re.search(r"\b(maito\w*|kerma\w*|voi(ta|n)?|litraa|kiloa|heti|tänää|tänään|huomenna|maanantai\w*|"
                 r"tarvitsen|tarviin|tilaa|kaura\w*|juoma\w*|ruokaa|safka|kiitti|joo|mä|kpl)\b", text, re.I):
        return "fi"
    if re.search(r"\b(mjölk|grädde|smör|liter|kilo|idag|imorgon|måndag\w*|tisdag\w*|onsdag\w*|torsdag\w*|"
                 r"fredag\w*|lördag\w*|söndag\w*|behöver|beställ|beställa|till|för|och|tack|ja|nej)\b", text, re.I):
        return "sv"
    return "en"


# --- store
def _read() -> dict:
    try:
        return json.loads(STORE.read_text()) if STORE.exists() else {}
    except (OSError, ValueError):
        return {}  # a broken store only loses open follow-ups; the chef can ask again


def save(buyer_id: str, kind: str, state: dict) -> str:
    cid = uuid4().hex
    now = time.time()
    with _lock:
        data = {k: v for k, v in _read().items() if v["expires"] > now}  # prune
        if len(data) >= MAX_OPEN:
            data = dict(sorted(data.items(), key=lambda kv: kv[1]["expires"])[-(MAX_OPEN - 1):])
        data[cid] = {"buyer_id": buyer_id, "kind": kind, "expires": now + FOLLOW_UP_TTL_S, **state}
        STORE.parent.mkdir(parents=True, exist_ok=True)
        tmp = STORE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, default=str))
        os.replace(tmp, STORE)
    return cid


def take(cid: str, buyer_id: str) -> dict:
    """The open conversation for this buyer, consumed (one answer per question). 404 if unknown, another buyer's, or
    expired: the same answer either way, so ids can't be probed."""
    with _lock:
        data = _read()
        entry = data.pop(cid, None)
        if entry is not None:
            tmp = STORE.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False, default=str))
            os.replace(tmp, STORE)
    if entry is None or entry["buyer_id"] != buyer_id or entry["expires"] <= time.time():
        raise HTTPException(404, detail="That question has expired or isn't yours. Please say the whole order again.")
    return entry


def peek(cid: str, buyer_id: str) -> dict:
    """Read an open question without consuming it; unrelated new requests keep the question answerable."""
    with _lock:
        entry = _read().get(cid)
    if entry is None or entry["buyer_id"] != buyer_id or entry["expires"] <= time.time():
        raise HTTPException(404, detail="That question has expired or isn't yours. Please say the whole order again.")
    return json.loads(json.dumps(entry, ensure_ascii=False))


def cart_state(request: dict, lines: list[dict] | None = None, held_items: list[int] | None = None) -> dict:
    """Bounded state for the one cart shared by all of its answerable follow-ups."""
    return {"request": json.loads(json.dumps(request, ensure_ascii=False)),
            "lines": json.loads(json.dumps(lines or [], ensure_ascii=False)),
            "held_items": list(held_items or [])}


# The v2 reading context is deliberately separate from the open follow-up store above.  Follow-up ids are short-lived
# workflow state; these buyer-scoped files are only the small amount of recent conversation context needed to understand
# the next message.
TURNS_TTL_S = 30 * 60
MAX_TURNS = 10
MAX_TURN_TEXT = 1_000
_turns_lock = threading.Lock()


def _history_path(buyer_id: str):
    digest = hashlib.sha256(str(buyer_id).encode("utf-8")).hexdigest()
    # Existing tests (and local callers) isolate the legacy follow-up store by replacing STORE. Keep the v2 history
    # beside that isolated store while production continues to use DATA_DIR/conversations.
    root = STORE.parent / "conversations" if STORE != _DEFAULT_STORE else config.DATA_DIR / "conversations"
    return root / f"{digest}.json"


def _read_history(path) -> dict:
    try:
        value = json.loads(path.read_text()) if path.exists() else {}
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _bounded_text(text: str) -> str:
    return str(text or "").strip()[:MAX_TURN_TEXT]


def _project_ingredient(ingredient) -> dict | None:
    if isinstance(ingredient, str):
        name = _bounded_text(ingredient)
        return {"name": name} if name else None
    if not isinstance(ingredient, dict):
        return None
    name = ingredient.get("name") or ingredient.get("product", {}).get("name_en") if isinstance(ingredient.get("product"), dict) else ingredient.get("name")
    name = _bounded_text(name)
    if not name:
        return None
    result = {"name": name}
    for key in ("amount", "unit"):
        if ingredient.get(key) is not None:
            result[key] = ingredient[key]
    return result


def _project_line(line) -> dict | None:
    if not isinstance(line, dict):
        return None
    product = line.get("product") if isinstance(line.get("product"), dict) else {}
    name = line.get("name") or product.get("name_en") or product.get("name") or product.get("name_fi")
    name = _bounded_text(name)
    if not name:
        return None
    result = {"name": name}
    price = line.get("price_cents", line.get("line_total_cents"))
    if price is not None:
        result["price_cents"] = price
    confidence = line.get("confidence", line.get("match_confidence"))
    if confidence is not None:
        result["confidence"] = confidence
    why = line.get("why") or line.get("reason")
    if why:
        result["why"] = _bounded_text(why)
    available = line.get("available")
    if available is None and isinstance(line.get("quote"), dict):
        available = line["quote"].get("orderable")
    if available is not None:
        result["available"] = bool(available)
    if "chosen" in line:
        result["chosen"] = bool(line.get("chosen"))
    if isinstance(line.get("quote"), dict) and line["quote"].get("price") is not None:
        result["unit_price"] = line["quote"]["price"]
    quantity_value = line.get("quantity")
    if isinstance(quantity_value, dict):
        requested = quantity_value.get("requested") if isinstance(quantity_value.get("requested"), dict) else quantity_value
        quantity = {key: requested[key] for key in ("amount", "unit") if requested.get(key) is not None}
        if quantity:
            result["quantity"] = quantity
    return result


def compact_card(body: dict | None) -> dict | None:
    """Keep only the bounded cart facts the next understanding pass may quote back to the chef."""
    if not isinstance(body, dict):
        return None
    result = {}
    ingredients = [_project_ingredient(item) for item in body.get("ingredients", [])]
    ingredients = [item for item in ingredients if item]
    if ingredients:
        result["ingredients"] = ingredients[:20]
    for source, target in (("lines", "lines"), ("held_lines", "held_lines")):
        lines = [_project_line(item) for item in body.get(source, [])]
        lines = [item for item in lines if item]
        if lines:
            result[target] = lines[:50]
    order = body.get("order") if isinstance(body.get("order"), dict) else {}
    order_status = order.get("status") or body.get("status")
    if order_status:
        result["order_status"] = order_status
    order_id = order.get("order_id") or body.get("order_id")
    if order_id:
        result["order_id"] = _bounded_text(order_id)
    for key in ("cart_total_cents", "requested_date", "question"):
        value = body.get(key)
        if value is not None and value != "":
            result[key] = _bounded_text(value) if isinstance(value, str) else value
    return result


def _pruned_history(data: dict, now: float) -> tuple[dict, bool]:
    changed = False
    cutoff = now - TURNS_TTL_S
    rows = []
    for row in data.get("turns", []):
        if not isinstance(row, dict) or row.get("role") not in {"user", "assistant"}:
            changed = True
            continue
        try:
            timestamp = float(row.get("time", 0))
        except (TypeError, ValueError):
            changed = True
            continue
        if timestamp < cutoff:
            changed = True
            continue
        text = _bounded_text(row.get("text"))
        if text != row.get("text"):
            changed = True
        rows.append({"role": row["role"], "text": text, "time": timestamp})
    bounded = rows[-MAX_TURNS:]
    if bounded != rows:
        changed = True
    data["turns"] = bounded
    card_time = data.get("last_card_time")
    if card_time is not None:
        try:
            expired = float(card_time) < cutoff
        except (TypeError, ValueError):
            expired = True
        if expired:
            data.pop("last_card", None)
            data.pop("last_card_time", None)
            changed = True
    return data, changed


def _write_history(path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
        os.replace(tmp, path)
    finally:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass


def record_turn(buyer_id: str, role: str, text: str, card: dict | None = None,
                pending: dict | None = None) -> None:
    """Atomically append one bounded turn and optionally replace the buyer's compact last card."""
    if role not in {"user", "assistant"}:
        raise ValueError("role must be user or assistant")
    now = time.time()
    path = _history_path(buyer_id)
    with _turns_lock:
        data, _ = _pruned_history(_read_history(path), now)
        data["turns"].append({"role": role, "text": _bounded_text(text), "time": now})
        data["turns"] = data["turns"][-MAX_TURNS:]
        if card is not None:
            projected = compact_card(card)
            if projected and any(key in projected for key in ("lines", "ingredients", "held_lines",
                                                               "cart_total_cents", "order")):
                data["last_card"] = projected
                data["last_card_time"] = now
        if pending is not None:
            if pending:
                data["pending_state"] = {"pending_slot": str(pending.get("pending_slot") or "")[:120],
                                          "choices": list(pending.get("choices") or [])[:4]}
            else:
                data.pop("pending_state", None)
        _write_history(path, data)


def turns(buyer_id: str) -> list[dict]:
    """Return this buyer's unexpired turns in chronological order."""
    now = time.time()
    path = _history_path(buyer_id)
    with _turns_lock:
        data = _read_history(path)
        data, changed = _pruned_history(data, now)
        if changed and path.exists():
            _write_history(path, data)
        return list(data.get("turns", []))


def last_card(buyer_id: str) -> dict | None:
    """Return the unexpired compact result card for this buyer, if one exists."""
    now = time.time()
    path = _history_path(buyer_id)
    with _turns_lock:
        data = _read_history(path)
        data, changed = _pruned_history(data, now)
        if changed and path.exists():
            _write_history(path, data)
        card = data.get("last_card")
        return json.loads(json.dumps(card, ensure_ascii=False)) if isinstance(card, dict) else None


def pending_state(buyer_id: str) -> dict | None:
    """Return the typed slot a chat turn is waiting for, bounded by the same history TTL."""
    now = time.time()
    path = _history_path(buyer_id)
    with _turns_lock:
        data, changed = _pruned_history(_read_history(path), now)
        if changed and path.exists():
            _write_history(path, data)
        value = data.get("pending_state")
        return json.loads(json.dumps(value, ensure_ascii=False)) if isinstance(value, dict) else None


def current_order(buyer_id: str) -> dict:
    """Return bounded order facts for this buyer's coming delivery days, without catalogue search or price lookups."""
    from . import catalogue, orders

    today = datetime.now(HELSINKI).date()
    rows = []
    for order in orders._store().values():
        if not isinstance(order, dict) or order.get("buyer_id") != buyer_id:
            continue
        if order.get("status") not in {"open", "pending", "pending_approval", "confirmed"}:
            continue
        try:
            requested = date.fromisoformat(str(order.get("requested_date")))
        except (TypeError, ValueError):
            continue
        if requested < today:
            continue
        lines = []
        for line in (order.get("lines") or [])[:50]:
            if not isinstance(line, dict):
                continue
            product = catalogue.get(str(line.get("product_id"))) or {}
            lines.append({key: value for key, value in {
                "name": line.get("name") or product.get("name_en") or product.get("name_fi") or line.get("product_id"),
                "amount": line.get("quantity"),
                "unit": line.get("unit"),
                "unit_price_cents": line.get("unit_price_cents"),
                "line_total_cents": line.get("line_total_cents"),
            }.items() if value is not None})
        rows.append({"order_id": str(order.get("id") or "")[:12], "requested_date": requested.isoformat(),
                     "status": order.get("status"), "lines": lines, "total_cents": order.get("total_cents")})
    rows.sort(key=lambda row: (row["requested_date"], row["order_id"]))
    rows = rows[:20]
    return {"orders": rows, "total_cents": sum(row.get("total_cents") or 0 for row in rows)}


# --- the spoken sentence
FI = {"For which delivery day?": "Mille päivälle toimitus?", "For how many guests?": "Kuinka monelle hengelle?",
      "I can only help with ordering from Valio. What do you need?": "Autan vain Valion tilauksissa. Mitä tarvitset?"}
SV = {"For which delivery day?": "Vilken leveransdag gäller?", "For how many guests?": "För hur många gäster?",
      "I can only help with ordering from Valio. What do you need?": "Jag kan bara hjälpa till med beställningar från Valio. Vad behöver du?"}


def _eur(cents: int | None, lang: str = "en") -> str:
    if cents is None:
        return ""
    unit = {"fi": "euroa", "sv": "euro", "en": "euros"}.get(lang, "euros")
    return f"{cents / 100:,.2f} {unit}".replace(",", " ")


def _line_text(line: dict, lang: str) -> str:
    quantity = line.get("quantity") if isinstance(line.get("quantity"), dict) else {}
    requested = quantity.get("requested") if isinstance(quantity.get("requested"), dict) else quantity
    amount, unit = requested.get("amount"), requested.get("unit")
    if isinstance(amount, float) and amount.is_integer():
        amount = int(amount)
    unit = {"ST": {"fi": "pakkausta", "sv": "förpackningar", "en": "packs"}.get(lang, "packs")}.get(unit, unit)
    product = line.get("product") if isinstance(line.get("product"), dict) else {}
    name = (product.get("name_en") or product.get("name_fi") or line.get("name") or "item").strip()
    return " ".join(str(value) for value in (amount, unit, name) if value not in (None, ""))


def speak(body: dict, lang: str) -> str:
    """One short sentence for the read-back: exactly what was decided or asked, built from the response fields."""
    assumption = next((value for value in body.get("assumptions") or []
                       if isinstance(value, str) and value.strip()), None)

    def finish(sentence: str) -> str:
        return f"{sentence.rstrip('.')} {assumption}." if assumption else sentence

    q = body.get("question")
    if q:
        if lang == "fi" and q in FI:
            return finish(FI[q])
        if lang == "sv" and q in SV:
            return finish(SV[q])
        if lang == "fi" and q.startswith("How much "):
            return finish("Kuinka paljon tarvitset?")
        if lang == "sv" and q.startswith("How much "):
            return finish("Hur mycket behöver du?")
        return finish(q if q.endswith("?") else q.split(". ")[0] + ".")
    order, decision = body.get("order"), body.get("decision") or {}
    all_lines = [ln for ln in body.get("lines", []) if isinstance(ln, dict)]
    lines = ([ln for ln in all_lines if ln.get("chosen")] if any("chosen" in ln for ln in all_lines)
             else all_lines)
    first = lines[0] if lines else None
    what = "; ".join(_line_text(line, lang) for line in lines)
    day = body.get("requested_date") or ""
    if order and order.get("status") == "confirmed":
        if lang == "fi":
            return finish(f"Tilattu: {what}, toimitus {day}.")
        if lang == "sv":
            return finish(f"Beställt: {what}, leverans {day}.")
        return finish(f"Ordered: {what}, arriving {day}.")
    if order and order.get("status") == "pending_approval":
        changes = [str(change.get("to")) for change in body.get("changes") or []
                   if isinstance(change, dict) and change.get("to")]
        change_note = (f"Changed to {', '.join(changes)}. " if changes and lang == "en" else
                       f"Muutettu: {', '.join(changes)}. " if changes and lang == "fi" else
                       f"Ändrad till {', '.join(changes)}. " if changes else "")
        if lang == "fi":
            return finish(f"{change_note}Odottaa hyväksyntääsi: {what}, {_eur(order.get('total_cents'), lang)}.")
        if lang == "sv":
            return finish(f"{change_note}Väntar på ditt godkännande: {what}, {_eur(order.get('total_cents'), lang)}.")
        return finish(f"{change_note}Waiting for your approval: {what}, {_eur(order.get('total_cents'), lang)}.")
    coverage = body.get("cart_coverage") or {}
    ingredient_count, in_cart = coverage.get("ingredients"), coverage.get("in_cart")
    if (isinstance(ingredient_count, int) and ingredient_count and isinstance(in_cart, int)
            and in_cart / ingredient_count < 0.6):
        needs_look = coverage.get("needs_look")
        if not isinstance(needs_look, int):
            needs_look = max(0, ingredient_count - in_cart)
        if not coverage.get("needs_look") and coverage.get("have"):
            return finish(f"I found {in_cart} of {ingredient_count} ingredients; the rest are already in your kitchen.")
        missing = body.get("not_found") or coverage.get("not_found") or []
        suffix = f" Not found: {', '.join(str(name) for name in missing)}." if missing else ""
        return finish((f"Löysin {in_cart} / {ingredient_count} ainesosaa; {needs_look} vaatii tarkistuksesi."
                       if lang == "fi" else f"I found {in_cart} of {ingredient_count} ingredients; "
                       f"{needs_look} need your look.") + suffix)
    if body.get("cart_total_cents") is not None:  # menu proposal
        coverage = body.get("cart_coverage") or {}
        ingredients, in_cart = coverage.get("ingredients"), coverage.get("in_cart")
        to_check = coverage.get("to_check") or 0
        not_found = len(coverage.get("not_found") or [])
        if ingredients is not None and in_cart is not None and (in_cart < ingredients or to_check or not_found):
            outstanding = to_check + not_found
            return finish((f"Osittainen kori: {in_cart} / {ingredients} ainesosaa on korissa; "
                           f"{outstanding} vaatii tarkistuksesi." if lang == "fi" else
                           f"Partial cart: {in_cart} of {ingredients} ingredients are in the cart; "
                           f"{outstanding} need your look.") +
                          (f" {not_found} ei löytynyt vielä." if lang == "fi" and not_found else
                           f" {not_found} are not found yet." if not_found else ""))
        return finish(f"Ostoskori valmis: {_eur(body['cart_total_cents'])}, tarkista oletukset." if lang == "fi"
                      else f"Cart ready: {_eur(body['cart_total_cents'])}. Check the assumptions before ordering.")
    primary = decision.get("primary_reason") or {}
    if first and primary.get("code") == "LOW_CONFIDENCE" and first.get("line_total_cents") is not None:
        name = (first["product"].get("name_en") or "").strip()
        return finish(f"Tarkista: {name}, {_eur(first['line_total_cents'])}. En ole varma, että tarkoitit tätä." if lang == "fi"
                      else f"Please check: {name}, {_eur(first['line_total_cents'])}. I'm not sure it's what you meant.")
    reason = primary.get("message", "Nothing was ordered.")
    return finish("Ei tilattu. Tarkista näytöltä." if lang == "fi" else f"Not ordered: {reason.split('. ')[0].rstrip('.')}.")


def date_answer(answer: str, today: date, date_from_text) -> date | None:
    """'Monday', 'tomorrow', 'maanantaiksi', '20.11.' → the date (via ask.date_from_text); a bare day number not."""
    d = date_from_text(answer, today)
    if d is None and re.search(r"\b(next week|ensi viikolla)\b", answer, re.I):
        d = today + timedelta(days=7 - today.weekday())  # next Monday
    return d
