"""The chef sets their rules in plain language (J3): Zoha's T09 compiler (compiler/trade_compiler) proposes a
Mandate; the approver confirms it; it is stored and the agent and front door use it at once.

Compile never saves. Saving refuses unanswered open questions, and big loosenings without `confirm_large_change`.
Every saved change is audited with the approver's name and an old → new summary.
"""
import asyncio
import json
from datetime import datetime, timezone
from uuid import uuid4

import httpx
from fastapi import HTTPException
from trade_compiler import compile_mandate
from trade_compiler.safety import DEFAULT_ORDER_LIMIT_CENTS
from trade_contracts import AuditEntry, AuditInput, Decision, HardRule, Mandate, PurchaseRequest
from trade_contracts import ReasonCode as C
from trade_contracts.common import PreferenceScope, RuleKind, UncertaintyPolicy

from . import agent, catalogue, config, gate, mandates, orders
from .auth import Principal

LARGE = 10  # a limit raised more than 10x (or removed) needs confirm_large_change


class RestLLM:
    """The compiler's LLMClient protocol over the same REST API the agent uses (no google-genai dependency).
    Sync on purpose: compile_mandate is sync and runs in a worker thread."""

    def generate_structured(self, prompt: str, schema: dict, model: str) -> dict:
        body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"responseMimeType": "application/json", "responseJsonSchema": schema,
                                     "temperature": 0}}
        r = httpx.post(f"{agent.GEMINI_URL}/{model}:generateContent", json=body, timeout=agent.GEMINI_TIMEOUT_S,
                       headers={"x-goog-api-key": config.GEMINI_API_KEY})
        r.raise_for_status()
        parts = r.json()["candidates"][0]["content"]["parts"]
        return json.loads("".join(p.get("text", "") for p in parts if not p.get("thought")))


# --- diff
def _eur(c) -> str:
    return "none" if c is None else gate.eur(int(c))


def _limits(m: Mandate | None) -> dict:
    if m is None:
        return {}
    allergens = set().union(*(gate._allergen_codes(str(v)) for v in gate._rules(m, RuleKind.EXCLUDED_ALLERGEN)))
    auto = gate._nums(m, RuleKind.AUTO_APPROVE_LIMIT_CENTS)
    rel = gate._nums(m, RuleKind.MIN_DELIVERY_RELIABILITY)
    price = gate._nums(m, RuleKind.MAX_UNIT_PRICE_CENTS)
    return {"auto_approve_limit_cents": min(auto) if auto else None, "per_line_cap_cents": m.per_line_cap_cents,
            "weekly_budget_cents": m.weekly_budget_cents, "excluded_allergens": allergens,
            "required_claims": {str(v) for v in gate._rules(m, RuleKind.REQUIRED_CLAIM)},
            "min_delivery_reliability": max(rel) if rel else None, "max_unit_price_cents": min(price) if price else None,
            "uncertainty_policy": m.uncertainty_policy.value, "blocklist": set(m.blocklist),
            "guidance": {g.text for g in m.guidance}, "expires_at": m.expires_at.isoformat() if m.expires_at else None}


def _ratio(before, after) -> float:
    """How many times looser a cap got; None = no cap at all = infinitely loose."""
    if after is None:
        return float("inf") if before is not None else 1.0
    if before is None:
        return 1.0
    return after / before if before else float("inf")


def diff(current: Mandate | None, proposed: Mandate) -> list[dict]:
    """Every field that changes, with direction (tighter / looser / changed) and whether saving it needs
    confirm_large_change. Money in net-of-VAT cents."""
    a, b, out = _limits(current), _limits(proposed), []

    def add(field, before, after, change, text, large=False):
        out.append({"field": field, "before": before, "after": after, "change": change, "text": text,
                    "needs_confirmation": large})

    for field, label in (("auto_approve_limit_cents", "auto-approve limit per order"),
                         ("per_line_cap_cents", "per-line cap"), ("weekly_budget_cents", "weekly budget"),
                         ("max_unit_price_cents", "max unit price")):
        x, y = a.get(field), b[field]
        if x != y:
            r = _ratio(x, y)
            looser = r > 1
            add(field, x, y, "looser" if looser else "tighter",
                f"{label}: {_eur(x)} → {_eur(y)}" + (" (no limit at all)" if y is None else ""),
                large=looser and r > LARGE)
    for field, label in (("excluded_allergens", "excluded allergen"), ("required_claims", "required claim"),
                         ("blocklist", "blocked product")):
        x, y = a.get(field, set()), b[field]
        for v in sorted(y - x):
            add(field, None, v, "tighter", f"new {label}: {catalogue.ALLERGEN_NAMES.get(v, v)}")
        for v in sorted(x - y):  # dropping a safety rule is never a casual edit
            add(field, v, None, "looser", f"{label} removed: {catalogue.ALLERGEN_NAMES.get(v, v)}", large=True)
    x, y = a.get("min_delivery_reliability"), b["min_delivery_reliability"]
    if x != y:
        looser = y is None or (x is not None and y < x)
        add("min_delivery_reliability", x, y, "looser" if looser else "tighter",
            f"on-time delivery floor: {'none' if x is None else f'{x:.0%}'} → {'none' if y is None else f'{y:.0%}'}",
            large=looser)  # any lower floor lets less reliable deliveries through without asking
    x, y = a.get("uncertainty_policy"), b["uncertainty_policy"]
    if x != y:
        looser = y == UncertaintyPolicy.APPROVE.value
        add("uncertainty_policy", x, y, "looser" if looser else "changed",
            f"when unsure: {x or 'ask'} → {y}", large=looser)
    x, y = a.get("expires_at"), b["expires_at"]
    if x != y:  # a later or removed expiry keeps the rules (and the agent's autonomy) alive longer
        looser = x is not None and (y is None or y > x)
        add("expires_at", x, y, "looser" if looser else "tighter",
            f"rules expire: {x or 'never'} → {y or 'never'}", large=looser)
    x, y = a.get("guidance"), b["guidance"]
    if x != y:
        add("guidance", sorted(x or []), sorted(y), "changed", "guidance changed (soft: ranking only)")
    return out


def assumptions(proposed: Mandate, loosened: tuple[str, ...]) -> list[str]:
    out = ["Money amounts are read as net of VAT (Valio's customer price without VAT).",
           "Rules apply to every order unless you said 'this order'.",
           "Anything you didn't mention goes back to the safe default (for example a per-line cap of "
           f"{gate.eur(proposed.per_line_cap_cents)}); see the changes list."]
    if proposed.uncertainty_policy is UncertaintyPolicy.ASK:
        out.append("When the agent can't verify something, it asks you.")
    return out + [f"Looser than the defaults: {x}." for x in loosened]


def with_default_limit(m: Mandate) -> Mandate:
    """The compiler documents that an empty mandate gets a EUR 500 auto-approve limit, but the gate applies no
    default (no rule = no spend check). Make it explicit, so 'not stated' can never mean 'unlimited'."""
    if gate._nums(m, RuleKind.AUTO_APPROVE_LIMIT_CENTS):
        return m
    return m.model_copy(update={"hard_rules": [*m.hard_rules, HardRule(
        kind=RuleKind.AUTO_APPROVE_LIMIT_CENTS, value=DEFAULT_ORDER_LIMIT_CENTS,
        source_text="Default: no auto-approve limit was stated.")]})


# --- routes' logic
async def compile_rules(text: str, who: Principal) -> dict:
    res = await asyncio.to_thread(compile_mandate, text, PreferenceScope.ALWAYS, llm=RestLLM(),
                                  buyer_id=who.buyer_id, mandate_id=f"{who.buyer_id}-draft")
    current, proposed = mandates.get(who.buyer_id), with_default_limit(res.mandate)
    defaulted = proposed is not res.mandate
    return {"proposed_mandate": proposed.model_dump(mode="json"),
            "diff_from_current": diff(current, proposed),
            "open_questions": [q.model_dump(mode="json") for q in proposed.open_questions],
            "assumptions": assumptions(proposed, res.loosened) + (
                [f"No auto-approve limit was stated, so the default {gate.eur(DEFAULT_ORDER_LIMIT_CENTS)} per order "
                 "applies."] if defaulted else []),
            "used_fallback": res.used_fallback, "injection_flagged": res.injection_flagged}


def invalid(m: Mandate) -> list[str]:
    """Rules the gate can't apply as standing rules. Rejected on save rather than stored and later silently lost
    (an invalid rule holds orders as MANDATE_INVALID; removing it must not be an invisible loosening)."""
    bad = []
    for r in m.hard_rules:
        if r.scope.value == "this_order":
            bad.append(f"'{r.kind.value}' is for one order only; standing rules can't be 'this order'.")
        if r.kind in (RuleKind.AUTO_APPROVE_LIMIT_CENTS, RuleKind.MAX_UNIT_PRICE_CENTS):
            v = gate._num(r.value)
            if v is None or v < 1 or v != int(v):
                bad.append(f"'{r.kind.value}' must be a whole number of cents, got {r.value!r}.")
        elif r.kind is RuleKind.MIN_DELIVERY_RELIABILITY:
            v = gate._num(r.value)
            if v is None or not 0 < v <= 1:
                bad.append(f"'min_delivery_reliability' must be between 0 and 1 (e.g. 0.9), got {r.value!r}.")
        elif r.kind is RuleKind.EXCLUDED_ALLERGEN and not gate._allergen_codes(str(r.value)):
            bad.append(f"Unknown allergen {r.value!r}; use a name like 'peanut' or a GS1 code like 'AP'.")
        elif r.kind is RuleKind.REQUIRED_CLAIM and not str(r.value).strip():
            bad.append("A required claim can't be empty.")
    return bad


def save(proposed: Mandate, confirm_large_change: bool, who: Principal, if_version: str | None = None) -> dict:
    proposed = with_default_limit(proposed)
    if problems := invalid(proposed):
        raise HTTPException(422, detail={"error": "These rules can't be saved as they are.", "problems": problems})
    if proposed.buyer_id != who.buyer_id:
        raise HTTPException(403, detail="This approver key may only set its own buyer's rules")
    if proposed.open_questions:
        raise HTTPException(422, detail={"error": "Answer the open questions first (or remove them), then save.",
                                         "open_questions": [q.question for q in proposed.open_questions]})
    mandates.check_version(who.buyer_id, if_version)  # early, clear 412; put() re-checks atomically
    current = mandates.get(who.buyer_id)
    changes = diff(current, proposed)
    big = [c for c in changes if c["needs_confirmation"]]
    if big and not confirm_large_change:
        raise HTTPException(409, detail={"error": "These changes loosen your rules a lot; resend with "
                                         "confirm_large_change=true if you mean them.", "changes": big})
    now = datetime.now(timezone.utc)
    saved = proposed.model_copy(update={"id": f"{who.buyer_id}-{now:%Y%m%dT%H%M%SZ}-{uuid4().hex[:6]}"})
    previous = mandates.put(saved, if_version)
    summary = "; ".join(c["text"] for c in changes) or "no changes"
    reasons = [gate._r(C.LIMIT_CHANGE_ATTEMPT, gate.INFO, f"{who.name} changed the rules: {c['text']} ({c['change']}).",
                       None, None, field=c["field"], change=c["change"],
                       before=json.dumps(c["before"], default=sorted), after=json.dumps(c["after"], default=sorted))
               for c in changes]
    entry = AuditEntry(
        id=str(uuid4()), timestamp=now, actor=f"human:{who.name}:mandate", input=AuditInput(
            mandate=saved, request=PurchaseRequest(id=saved.id, buyer_id=who.buyer_id, created_at=now,
                                                   text=f"Rules changed by {who.name} (was {current.id if current else 'none'}): {summary}")),
        decision=Decision(request_id=saved.id, outcome="AUTO", reasons=reasons, rules_version=agent.RULES_VERSION,
                          decided_at=now))
    try:
        orders._append_audit(entry)
    except Exception:  # noqa: BLE001 - no rule change without its audit entry
        mandates.restore(who.buyer_id, previous)
        raise HTTPException(503, detail="The change couldn't be audited, so it was not saved. Retry shortly.") from None
    return {"mandate": saved.model_dump(mode="json"), "changes": changes, "audit_id": entry.id,
            "version": mandates.version(saved)}
