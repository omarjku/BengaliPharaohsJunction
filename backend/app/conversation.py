"""Conversational follow-ups: the chef's spoken or typed ANSWER to the agent's question continues the same request.

When /api/agent/ask asks for one thing it can continue from (the amount of an item, the delivery day, the number of
guests, or "order again?"), it stores the original request for FOLLOW_UP_TTL_S, per buyer, under DATA_DIR, and
returns a conversation_id. The answer may fill ONLY the field that was asked: it is parsed deterministically
(numbers in words too, English and Finnish), and everything else, the buyer, the limits and the other items, comes
from the stored request and the server-side mandate. The request then re-runs through every check.
Also here: speak(), the one-sentence spoken version of any /ask response.
"""
import json
import os
import re
import threading
import time
from datetime import date, timedelta
from uuid import uuid4

from fastapi import HTTPException

from . import config, quantity

STORE = config.DATA_DIR / "conversations.json"
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
    return "fi" if re.search(r"[äö]|\b(maito\w*|kerma\w*|voi(ta|n)?|litraa|kiloa|heti|tänään|huomenna|maanantai\w*|"
                             r"tarvitsen|tilaa|kpl)\b", text, re.I) else "en"


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


# --- the spoken sentence
FI = {"For which delivery day?": "Mille päivälle toimitus?", "For how many guests?": "Kuinka monelle hengelle?",
      "I can only help with ordering from Valio. What do you need?": "Autan vain Valion tilauksissa. Mitä tarvitset?"}


def _eur(cents: int | None) -> str:
    return "" if cents is None else f"{cents / 100:,.2f} euros".replace(",", " ")


def speak(body: dict, lang: str) -> str:
    """One short sentence for the read-back: exactly what was decided or asked, built from the response fields."""
    q = body.get("question")
    if q:
        if lang == "fi" and q in FI:
            return FI[q]
        if lang == "fi" and q.startswith("How much "):
            return "Kuinka paljon tarvitset?"
        return q if q.endswith("?") else q.split(". ")[0] + "."
    order, decision = body.get("order"), body.get("decision") or {}
    lines = [ln for ln in body.get("lines", []) if ln.get("chosen")]
    first = lines[0] if lines else None
    what = ""
    if first and first.get("quantity"):
        qd = first["quantity"]
        what = f"{qd['requested']['amount']:g} {qd['requested']['unit']} {(first['product'].get('name_en') or '').strip()}"
    day = body.get("requested_date") or ""
    if order and order.get("status") == "confirmed":
        return (f"Tilattu: {what}, toimitus {day}." if lang == "fi" else f"Ordered: {what}, arriving {day}.")
    if order and order.get("status") == "pending_approval":
        reason = (decision.get("primary_reason") or {}).get("message", "")
        if lang == "fi":
            return f"Tarvitsee hyväksyntäsi: {what}, {_eur(order.get('total_cents'))}."
        return f"Needs your OK: {what}, {_eur(order.get('total_cents'))}. {reason.split('. ')[0]}."
    if body.get("cart_total_cents") is not None:  # menu proposal
        return (f"Ostoskori valmis: {_eur(body['cart_total_cents'])}, tarkista oletukset." if lang == "fi"
                else f"Cart ready: {_eur(body['cart_total_cents'])}. Check the assumptions before ordering.")
    primary = decision.get("primary_reason") or {}
    if first and primary.get("code") == "LOW_CONFIDENCE" and first.get("line_total_cents") is not None:
        name = (first["product"].get("name_en") or "").strip()
        return (f"Tarkista: {name}, {_eur(first['line_total_cents'])}. En ole varma, että tarkoitit tätä." if lang == "fi"
                else f"Please check: {name}, {_eur(first['line_total_cents'])}. I'm not sure it's what you meant.")
    reason = primary.get("message", "Nothing was ordered.")
    return ("Ei tilattu. Tarkista näytöltä." if lang == "fi" else f"Not ordered: {reason.split('. ')[0].rstrip('.')}.")


def date_answer(answer: str, today: date, date_from_text) -> date | None:
    """'Monday', 'tomorrow', 'maanantaiksi', '20.11.' → the date (via ask.date_from_text); a bare day number not."""
    d = date_from_text(answer, today)
    if d is None and re.search(r"\b(next week|ensi viikolla)\b", answer, re.I):
        d = today + timedelta(days=7 - today.weekday())  # next Monday
    return d
