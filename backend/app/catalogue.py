"""Valio Aimo product catalogue: a slim, searchable index built from the 83 MB product file.

The raw file is NOT in git (Valio's dataset is for Junction 2026 only). Order of sources:
1. data/catalogue_slim.json (built before, fast)
2. data/valio_aimo_junction26_*.json/csv downloaded by hand (local dev)
3. Valio's download endpoints (Render): streamed to a temp file, never loaded whole.
json.load of the raw file peaks ~680 MB; the Starter instance has 512 MB, so the build streams with ijson.
"""
import csv
import json
import logging
import re
import tempfile
import threading
from pathlib import Path

import httpx
import ijson

from . import config
from .valio import USER_AGENT

DATA = Path(__file__).resolve().parents[2] / "data"
SLIM = DATA / "catalogue_slim.json"
RAW = {
    "products": DATA / "valio_aimo_junction26_product_data.json",
    "carbon": DATA / "valio_aimo_junction26_carbon_footprint.csv",
    "reliability": DATA / "valio_aimo_junction26_delivery_reliability.csv",
}
ENDPOINT = {"products": "products", "carbon": "carbon-footprint", "reliability": "delivery-reliability"}
SLIM_VERSION = 3

# GS1 allergen codes seen in the data; only well-known ones are labelled, others stay as codes.
ALLERGEN_NAMES = {"AM": "milk", "AE": "egg", "AF": "fish", "AN": "tree nuts", "AP": "peanuts", "AY": "soy",
                  "AW": "gluten (cereals)", "AC": "crustaceans", "AS": "sesame", "BC": "celery", "BM": "mustard",
                  "AU": "sulphites", "NL": "lupin", "UM": "molluscs", "UW": "wheat"}
_INFERRED_WORDS = {
    "AF": ("fish", "salmon", "lohi", "trout", "kirjolohi", "tuna", "tonnikala", "cod", "turska", "herring",
           "silakka", "silli", "whitefish", "siika", "pike", "hauki", "perch", "ahven", "zander", "kuha",
           "pollock", "seiti", "anchovy", "sardine", "mackerel", "makrilli", "char", "nieriä", "roe", "mäti"),
    "AC": ("shrimp", "katkarapu", "prawn", "crab", "lobster"),
    "UM": ("mussel", "simpukka", "squid"),
    "AM": ("milk", "maito", "cream", "kerma", "cheese", "juusto", "butter", "voi", "yoghurt", "jogurtti", "rahka"),
    "AE": ("egg", "kananmuna"),
    "AW": ("wheat", "vehnä", "noodle", "pasta", "bread", "gluten"),
    "UW": ("wheat", "vehnä", "noodle", "pasta", "bread"),
}

_products: dict[str, dict] = {}
_ready = threading.Event()
_error: str | None = None
_lock = threading.Lock()


def _text(items: list | None, lang: str) -> str | None:
    for x in items or []:
        if x.get("language") == lang:
            return x.get("value")
    return None


# Short words that are prefixes of unrelated words (eggplant, charcuterie, voimakas, code): whole words only.
_WHOLE_WORDS = {"egg", "char", "cod", "roe", "voi", "pike", "tuna", "crab"}


def _infer_allergens(p: dict, names: dict) -> list[str]:
    hay = " ".join(str(value) for value in (names.get("en"), names.get("fi"), p.get("category")) if value).lower()
    inferred = set()
    for code, words in _INFERRED_WORDS.items():
        for word in words:
            tail = r"(?!\w)" if word in _WHOLE_WORDS else ""
            match = re.search(rf"(?<!\w){re.escape(word)}{tail}", hay)
            if not match:
                continue
            rest = hay[match.end():]
            word_end = re.match(r"\w*", rest).group(0)
            if re.search(r"t(o|ö)n|tt(o|ö)m", word_end) or re.match(r"\w*(\s+(and|&|ja)\s+\w+)?[\s-]*(free|vapaa)", rest):
                continue
            if code == "AM" and re.search(r"(?:coconut|oat|soy|almond|rice|peanut|kookos|kaura|soija|manteli|riisi|maapähkinä)\s*", hay[:match.start()]):
                continue
            inferred.add(code)
            break
    return sorted(inferred)


def _slim(p: dict) -> dict:
    s = p.get("synkkaData") or {}
    allergens = {"contains": [], "may_contain": [], "free_from": [], "undeclared": []}
    claims, labels = [], []
    for c in s.get("classifications") or []:
        if c["name"] == "allergen":
            for v in c.get("values", []):
                key = {"CONTAINS": "contains", "MAY_CONTAIN": "may_contain", "UNDECLARED": "undeclared"}.get(v.get("unit"))
                if key:
                    allergens[key].append(v["id"])
        elif c["name"] == "nonAllergen":
            for v in c.get("values", []):
                key = "free_from" if v.get("unit") == "FREE_FROM" else None
                if key:
                    allergens[key].append(v["id"])
        elif c["name"] == "nutritionalClaim":
            claims += [v["id"] for v in c.get("values", [])]
        elif c["name"] == "packagingMarkedLabel":
            labels += [v["id"] for v in c.get("values", [])]
    allergen_data = "missing" if not any(allergens.values()) else "declared"
    # Name-based guesses only fill a gap: when Valio declares allergens, its declaration wins (no false declines).
    inferred = [] if allergen_data != "missing" else [code for code in _infer_allergens(p, {"en": _text(s.get("names"), "en"), "fi": _text(s.get("names"), "fi")})
                if code not in set(allergens["contains"]) | set(allergens["may_contain"]) | set(allergens["free_from"])]
    if allergen_data == "missing":
        allergens["undeclared"] = sorted(ALLERGEN_NAMES)
    allergens["inferred"] = inferred
    base = next((u for u in s.get("unitConversions") or [] if u.get("synkkaPackagingType") == "BASE_UNIT_OR_EACH"), {})
    return {
        "id": p["id"],
        "name_en": _text(s.get("names"), "en"),
        "name_fi": _text(s.get("names"), "fi"),
        "brand": s.get("brand"),
        "category": p.get("category"),
        "vendor": p.get("vendorName"),
        "origin": p.get("countryOfOrigin"),
        "sales_unit": p.get("salesUnit"),
        "base_unit": p.get("baseUnit"),
        "lot_size": p.get("allowedLotSize"),
        "units": {u["unitId"]: u["sizeInBaseUnits"] for u in p.get("units") or []},
        # per consumer unit; both kept because liquids need volume, solids need weight (data units vary: LTR/MLT/KGM/GRM)
        "net_weight": base.get("netWeight"),
        "volume": base.get("volume"),
        "temperature_class": p.get("temperatureCondition"),
        "claims": claims,
        "labels": labels,
        "allergens": allergens,
        "allergen_data": allergen_data,
        "deposits": p.get("deposits") or [],
        "substitutes": [x["substituteProduct"] for x in p.get("substitutions") or []],
        "vat": s.get("vatCode"),
    }


def _fetch(kind: str, dest: Path) -> None:
    """Stream one Valio download to `dest`. The endpoint answers 307 → file URL; we follow it ourselves so the
    API key is only ever sent to Valio's own host (a signed storage URL elsewhere must not receive it)."""
    url = f"{config.VALIO_BASE_URL}/api/{ENDPOINT[kind]}/download"
    valio_host = httpx.URL(config.VALIO_BASE_URL).host
    for _ in range(5):  # bounded redirect chain
        target = httpx.URL(url)
        headers = {"User-Agent": USER_AGENT}
        if target.host == valio_host and target.scheme == "https":
            headers["X-API-Key"] = config.VALIO_API_KEY
        with httpx.stream("GET", url, headers=headers, follow_redirects=False, timeout=120) as r:
            if r.is_redirect:
                url = str(target.join(r.headers["location"]))
                continue
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_bytes(1 << 20):
                    f.write(chunk)
            return
    raise RuntimeError("too many redirects downloading Valio data")


def _csv_map(path: Path, col: str) -> dict[str, float]:
    with open(path, newline="") as f:
        return {row["productId"]: float(row[col]) for row in csv.DictReader(f) if row.get(col)}


def build_slim() -> None:
    """Build data/catalogue_slim.json from local raw files, downloading any that are missing."""
    DATA.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        src = {}
        for kind, path in RAW.items():
            if path.exists():
                src[kind] = path
            else:
                src[kind] = Path(tmp) / path.name
                _fetch(kind, src[kind])
        carbon = _csv_map(src["carbon"], "AVG kg CO2-eq/kg")
        reliability = _csv_map(src["reliability"], "deliveryReliability")
        out = []
        with open(src["products"], "rb") as f:
            for p in ijson.items(f, "item", use_float=True):  # one product at a time: low memory
                if p.get("deleted"):
                    continue
                s = _slim(p)
                s["carbon_kg_per_kg"] = carbon.get(s["id"])
                s["delivery_reliability"] = reliability.get(s["id"])
                out.append(s)
    SLIM.write_text(json.dumps({"version": SLIM_VERSION, "products": out}, ensure_ascii=False))


def load() -> None:
    """Load (building first if needed). Safe to call from a background thread; sets readiness."""
    global _products, _error
    with _lock:
        if _ready.is_set():
            return
        try:
            if not SLIM.exists():
                build_slim()
            slim = json.loads(SLIM.read_text())
            if not isinstance(slim, dict) or slim.get("version") != SLIM_VERSION:
                build_slim()
                slim = json.loads(SLIM.read_text())
            _products = {p["id"]: p for p in slim["products"]}
            _error = None
            _ready.set()
        except Exception:
            # Full details (may include signed download URLs or paths) stay in the server log only.
            logging.getLogger(__name__).exception("catalogue build/load failed")
            _error = "catalogue_unavailable"


def status() -> dict:
    return {"ready": _ready.is_set(), "products": len(_products), "error": _error}


def get(product_id: str) -> dict | None:
    return _products.get(product_id)


_WORD = re.compile(r"[\wäöåÄÖÅ]+")
KITCHEN_SYNONYMS = {
    "oat milk": ["oat drink", "kaurajuoma", "kauramaito"],
    "oat drink": ["oat milk", "kaurajuoma", "kauramaito"],
    "kaurajuoma": ["oat milk", "oat drink", "kauramaito"],
    "kauramaito": ["oat milk", "oat drink", "kaurajuoma"],
    "almond milk": ["almond drink", "mantelijuoma", "mantelimaito"],
    "almond drink": ["almond milk", "mantelijuoma", "mantelimaito"],
    "mantelijuoma": ["almond milk", "almond drink", "mantelimaito"],
    "mantelimaito": ["almond milk", "almond drink", "mantelijuoma"],
    "plant milk": ["plant drink", "kasvijuoma", "kasvimaito"],
    "plant drink": ["plant milk", "kasvijuoma", "kasvimaito"],
    "kasvijuoma": ["plant milk", "plant drink", "kasvimaito"],
    "cream": ["kerma", "whipping cream", "cooking cream"],
    "kerma": ["cream", "whipping cream", "ruokakerma"],
    "sour cream": ["smetana", "kermaviili"],
    "smetana": ["sour cream", "kermaviili"],
    "kermaviili": ["sour cream", "smetana"],
}


def synonym_queries(query: str) -> list[str]:
    """Small deterministic kitchen vocabulary; catalogue.search itself remains an every-term search."""
    key = " ".join(str(query or "").lower().split())
    return list(KITCHEN_SYNONYMS.get(key, []))


def search(query: str = "", claims: list[str] | None = None, exclude_allergens: list[str] | None = None,
           strict_may_contain: bool = False, category: str | None = None, limit: int = 20) -> list[dict]:
    """Keyword search over English + Finnish names and brand, with hard filters.
    - claims: every listed claim must be present (e.g. FREE_FROM_LACTOSE)
    - exclude_allergens: drop products that CONTAIN them (and MAY_CONTAIN them if strict_may_contain)
    ponytail: token overlap scoring; switch to embeddings if lexical recall is too low for menu-to-cart."""
    terms = [t.lower() for t in _WORD.findall(query)]
    need, avoid = set(claims or []), set(exclude_allergens or [])
    hits = []
    for p in _products.values():
        if need - set(p["claims"]):
            continue
        allergens = p.get("allergens") or {}
        risky = (set(allergens.get("contains") or []) | set(allergens.get("inferred") or []) |
                 (set(allergens.get("may_contain") or []) if strict_may_contain else set()))
        if avoid & risky or (category and p["category"] != category):
            continue
        hay = " ".join(filter(None, [p["name_en"], p["name_fi"], p["brand"]])).lower()
        words = _WORD.findall(hay)
        matched = [t for t in terms if t in hay]
        if len(matched) < len(terms):  # every term must appear (at least as a substring)
            continue
        score = sum(2 if t in words else 1 for t in matched) if terms else 1  # whole-word hits rank higher
        hits.append((score, p))
    # ties → shorter names first: "milk drink 1 l lactose free" beats "12 x Starbucks latte … lactose free"
    hits.sort(key=lambda x: (-x[0], len(x[1]["name_en"] or x[1]["name_fi"] or ""), x[1]["id"]))
    return [dict(p, score=s) for s, p in hits[:limit]]
