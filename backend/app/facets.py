"""Hard product attributes the chef WROTE (lactose-free, unsalted, organic, fat %...), checked against a catalogue
product. Deterministic and bilingual; it only ever ADDS a question, never permits anything.

Why: the engine scored the chosen product on the agent's own rewritten item ("butter 500 g"), where the attribute
had been dropped or moved. The chef's original words are the source of truth: every hard attribute in them must be
positively evidenced by the product (its claims, labels or name), or the line cannot be auto-approved.

Dietary needs (lactose-free, gluten-free, vegan, allergens) are NOT here: agent.DIETARY / diet.py own them, with
claims filters and "safe by nature" reasoning (carrots are lactose-free without a label).

`need` concepts require positive evidence ("unsalted": the name must say so). Others only conflict when the product
states the opposite ("salted" vs a product named unsalted). General vocabulary, no per-request logic."""
import re

_NEG_SALT = r"(?<![a-zäöå])(?:salted|suolattu\w*|suolaa(?!maton))"
_POS_UNSALTED = r"unsalted|saltless|no added salt|suola\w*?ton\w*|suolaamaton|salt[- ]free"

CONCEPTS = {
    "organic": {"req": r"organic|luomu\w*", "pos": r"organic|luomu\w*", "labels": {"EU_ORGANIC_FARMING", "KRAV_MARK",
                "SOIL_ASSOCIATION_ORGANIC_SYMBOL"}, "need": True, "terms": ("organic", "luomu")},
    "unsalted": {"req": r"unsalted|saltless|(?:no|without)\s+(?:added\s+)?salt|suola\w*?ton\w*|suolaamaton|ilman\s+suolaa",
                 "pos": _POS_UNSALTED, "neg": _NEG_SALT, "need": True, "terms": ("unsalted", "suolaamaton")},
    "salted": {"req": _NEG_SALT, "pos": _NEG_SALT, "neg": _POS_UNSALTED, "need": False, "terms": ()},
}
_PERCENT = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:%|prosentti\w*|percent)", re.I)
_FAT_FREE = re.compile(r"fat[\s-]*free|skimmed|rasvaton\w*", re.I)


def _name_text(product: dict) -> str:
    return " ".join(str(product.get(k) or "") for k in ("name_en", "name_fi", "brand")).lower()


def _percents(text: str) -> set[float]:
    return {float(m.replace(",", ".")) for m in _PERCENT.findall(text)}


def request_facets(text: str) -> dict:
    """The hard attributes written in the chef's words: {"concepts": [names], "percent": {fat %...}}."""
    low = str(text or "").lower()
    found = [name for name, c in CONCEPTS.items() if re.search(c["req"], low)]
    if "unsalted" in found and "salted" in found:  # "salted" inside "unsalted" is the same word, not a second ask
        found.remove("salted")
    return {"concepts": found, "percent": _percents(low)}


def has_any(facets: dict) -> bool:
    return bool(facets.get("concepts") or facets.get("percent"))


def check(facets: dict, product: dict) -> list[tuple[str, str, str]]:
    """[(kind, concept, detail)] where kind is "conflict" (the product says otherwise) or "missing" (nothing in its
    claims, labels or name backs the attribute). Empty list: every written attribute is evidenced."""
    name = _name_text(product)
    claims, labels = set(product.get("claims") or []), set(product.get("labels") or [])
    out = []
    for concept in facets.get("concepts") or []:
        c = CONCEPTS[concept]
        evidenced = bool(re.search(c["pos"], name) or claims & c.get("claims", set()) or labels & c.get("labels", set()))
        says_opposite = bool(c.get("neg") and re.search(c["neg"], name))
        if concept == "salted":
            evidenced = not re.search(_POS_UNSALTED, name)
        if says_opposite and not (concept != "salted" and evidenced):
            out.append(("conflict", concept, f"its name says the opposite of {concept}"))
        elif c["need"] and not evidenced:
            out.append(("missing", concept, f"nothing in its name or labels says {concept}"))
    wanted = facets.get("percent") or set()
    if wanted:
        have = {0.0} if _FAT_FREE.search(name) else _percents(name)
        if have and not have & wanted:
            out.append(("conflict", "fat %", f"it states {', '.join(f'{x:g}' for x in sorted(have))} % while "
                                              f"{', '.join(f'{x:g}' for x in sorted(wanted))} % was asked"))
        elif not have:
            out.append(("missing", "fat %", "its name states no fat percentage"))
    return out


def penalty(facets: dict, product: dict) -> int:
    """Ranking key part: conflicts count double, unverified attributes once. 0 = fully agrees."""
    return sum(2 if kind == "conflict" else 1 for kind, *_ in check(facets, product))


def search_terms(facets: dict) -> list[str]:
    """Extra catalogue words to search together with the item's product words (English and Finnish names)."""
    return [t for concept in facets.get("concepts") or [] for t in CONCEPTS[concept]["terms"]]


def question(facets_found: list[tuple[str, str, str]], name: str) -> str:
    kinds = ", ".join(sorted({concept for _, concept, _ in facets_found}))
    return (f"You asked for {kinds}, but I can't confirm that for {name}: "
            f"{'; '.join(dict.fromkeys(detail for *_, detail in facets_found))}. "
            "Is it still fine, or should I look for another product?")
