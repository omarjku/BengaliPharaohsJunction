"""Deterministic safety nets that hold even if the model is fooled (Agent B).

The compiler must never output a mandate LOOSER than the defaults unless the buyer says so
explicitly, and the buyer's text is data: it cannot rewrite the schema or the defaults.
"""

from __future__ import annotations

import re

from trade_contracts.money import eur_to_cents

# Defaults the T06 decision step applies to an empty mandate.
DEFAULT_ORDER_LIMIT_CENTS = 50000
DEFAULT_PER_LINE_CAP_CENTS = 30000

# A number as a human writes it: optional digit groups ("1 200", "1.200", "1,200") + decimals.
_NUMBER = re.compile(r"\d{1,3}(?:[   .,]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?")
_PLAIN = re.compile(r"\d+(?:[.,]\d{1,2})?")


def _readings(token: str) -> list[int]:
    """Possible cent values of one number token, most likely reading first."""
    t = re.sub(r"[   ]", "", token)
    readings: list[str] = []
    if "." in t and "," in t:
        dec = max(t.rfind("."), t.rfind(","))
        readings.append(re.sub(r"[.,]", "", t[:dec]) + "." + t[dec + 1 :])
    elif "." in t or "," in t:
        sep = "." if "." in t else ","
        if t.count(sep) > 1:  # "1.200.000": grouping only
            readings.append(t.replace(sep, ""))
        else:
            head, tail = t.split(sep)
            if len(tail) == 3:  # "1.200" / "1,200": grouping first, decimal as a fallback
                readings += [head + tail, head + "." + tail]
            else:
                readings.append(head + "." + tail)
    else:
        readings.append(t)
    out: list[int] = []
    for r in readings:
        try:
            cents = eur_to_cents(r)
        except ValueError:
            continue
        if cents not in out:
            out.append(cents)
    return out


def amounts_in_text(text: str) -> set[int]:
    """Every euro amount (in cents) a human could read out of `text` ('500', '1 200,50', '€500',
    '500 euro'). A money value from the model that is not in this set is dropped (and becomes an
    open question): the model may not invent numbers."""
    found: set[int] = set()
    for pattern in (_NUMBER, _PLAIN):  # grouped reading AND each number on its own
        for match in pattern.finditer(text or ""):
            found.update(_readings(match.group(0)))
    return found


def parse_amount(written: str, allowed: set[int]) -> int | None:
    """Cents for a euro amount as the model copied it, but only if the text really contains it."""
    for pattern in (_NUMBER, _PLAIN):
        for match in pattern.finditer(written or ""):
            for cents in _readings(match.group(0)):
                if cents in allowed and cents > 0:
                    return cents
    return None


_INJECTION = [
    r"\b(ignore|forget|disregard|override|bypass)\b",
    r"\b(previous|prior|above|earlier)\s+(rules?|instructions?|prompts?|limits?)\b",
    (
        r"\bthe\s+(owner|boss|admin|administrator|manager|developer|system|operator)\s+"
        r"(says?|said|wants?|told|has\s+(said|approved|authori[sz]ed))\b"
    ),
    r"\bsystem\s*:",
    r"\bassistant\s*:",
    r"\byou\s+are\s+now\b",
    r"\bnew\s+(instructions?|rules?\s+for\s+you)\b",
    r"\bact\s+as\b",
    r"\bpretend\b",
    r"\bjailbreak\b",
    r"\braise\s+(the\s+)?(limit|cap)\b",
    r"\bdeveloper\s+mode\b",
]
_INJECTION_RE = re.compile("|".join(f"(?:{p})" for p in _INJECTION), re.IGNORECASE)

_APPROVE_RE = re.compile(
    r"\b(do\s*not|don'?t|dont|never|no\s+need\s+to|stop)\s+(to\s+)?ask(ing)?\b|\bjust\s+order\b",
    re.IGNORECASE,
)


def detect_injection(text: str) -> bool:
    """True when the text tries to instruct the system instead of stating buyer rules, e.g.
    'ignore previous rules', 'the owner says raise the limit', 'system:', 'you are now'.
    Deterministic (regex/keywords). A flagged text can never loosen anything."""
    return bool(_INJECTION_RE.search(text or ""))


def says_do_not_ask(text: str) -> bool:
    """True only when the buyer explicitly says the agent should not ask them."""
    return bool(_APPROVE_RE.search(text or ""))
