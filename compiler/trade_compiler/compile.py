"""compile_mandate(): plain-language rules -> a PROPOSED Mandate (Agent B).

The result is a proposal: it becomes the active mandate only after the human confirms it.
`loosened` lists everything that is looser than the defaults so the UI can highlight it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import ValidationError
from trade_contracts import Mandate, OpenQuestion
from trade_contracts.common import (  # not exported at top level yet (T02.2 gap)
    PreferenceScope,
    RuleKind,
    UncertaintyPolicy,
)
from trade_contracts.mandate import HardRule, Preference

from .llm import DEFAULT_MODELS, LLMClient
from .prompt import build_prompt
from .safety import (
    DEFAULT_ORDER_LIMIT_CENTS,
    DEFAULT_PER_LINE_CAP_CENTS,
    amounts_in_text,
    detect_injection,
    parse_amount,
    says_do_not_ask,
)
from .schema import OUTPUT_SCHEMA, CompilerOutput, ExtractedMoney

_FALLBACK_QUESTION = "I couldn't read your rules; please say them again."
_ISO_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_TZ = "Europe/Helsinki"
_INJECTION_WHY = (
    "Your text looked like an instruction to the system, so nothing looser than the defaults "
    "was applied."
)


@dataclass(frozen=True)
class CompileResult:
    mandate: Mandate
    loosened: tuple[str, ...] = ()  # human-readable notes, e.g. "auto-approve limit 1200 EUR > 500"
    used_fallback: bool = False  # True when Gemini output was unusable (no hard rules + a question)
    injection_flagged: bool = False  # True when the text tried to instruct the system

    @property
    def open_questions(self) -> list[OpenQuestion]:
        return self.mandate.open_questions


def _eur(cents: int) -> str:
    return f"{cents // 100}" if cents % 100 == 0 else f"{cents / 100:.2f}"


def _fallback(mandate_id: str, buyer_id: str, *, injection: bool = False) -> CompileResult:
    mandate = Mandate(
        id=mandate_id,
        buyer_id=buyer_id,
        open_questions=[OpenQuestion(question=_FALLBACK_QUESTION)],
    )
    return CompileResult(mandate=mandate, used_fallback=True, injection_flagged=injection)


def _ask_model(llm: LLMClient, prompt: str) -> CompilerOutput | None:
    """One call, plus one retry with the validation error. None = unusable."""
    model = DEFAULT_MODELS[0]
    raw = llm.generate_structured(prompt, OUTPUT_SCHEMA, model)
    try:
        return CompilerOutput.model_validate(raw)
    except (ValidationError, ValueError, TypeError) as exc:
        error = str(exc)[:800]
    retry = (
        f"{prompt}\nYour previous answer was not valid for the required JSON schema:\n{error}\n"
        "Return a corrected JSON object only."
    )
    raw = llm.generate_structured(retry, OUTPUT_SCHEMA, model)
    try:
        return CompilerOutput.model_validate(raw)
    except (ValidationError, ValueError, TypeError):
        return None


def compile_mandate(
    text: str,
    scope: PreferenceScope = PreferenceScope.ALWAYS,
    *,
    llm: LLMClient | None = None,
    buyer_id: str = "buyer",
    mandate_id: str = "mandate-draft",
) -> CompileResult:
    """Steps:
    1. empty/blank text -> fallback (no model call): no hard rules + an open question.
    2. build_prompt -> llm.generate_structured(prompt, OUTPUT_SCHEMA, model).
    3. parse into CompilerOutput; on failure retry ONCE with the error message; then fallback.
    4. convert: euros as written -> eur_to_cents(); scope = cue, else `scope` (an 'always' is
       never turned into 'this_order' or the reverse); ambiguous -> open_questions, not rules;
       claims/origin -> guidance + open question; never raise.
    5. safety: drop money not present in the text; detect_injection; anything looser than the
       defaults (limit above 50000 cents, per-line cap above 30000, policy 'approve') is added to
       `loosened`, and is DROPPED (plus an open question) when the text was flagged as injection.
    6. build the Mandate (contract v0.2) and return CompileResult.
    """
    try:
        if not isinstance(text, str) or not text.strip():
            return _fallback(mandate_id, buyer_id)
        if llm is None:
            from .llm import GeminiLLM  # lazy: tests never need the real backend

            llm = GeminiLLM()
        out = _ask_model(llm, build_prompt(text, scope))
        if out is None:
            return _fallback(mandate_id, buyer_id, injection=detect_injection(text))
        return _convert(out, text, scope, buyer_id, mandate_id)
    except Exception:  # noqa: BLE001 - compile_mandate never raises
        return _fallback(mandate_id, buyer_id)


def _convert(
    out: CompilerOutput, text: str, scope: PreferenceScope, buyer_id: str, mandate_id: str
) -> CompileResult:
    flagged = detect_injection(text)
    allowed = amounts_in_text(text)
    source = text.strip()[:200]
    questions: list[OpenQuestion] = [
        OpenQuestion(question=q.question.strip(), why=q.why)
        for q in out.open_questions
        if q.question.strip()
    ]
    loosened: list[str] = []
    rules: list[HardRule] = []
    guidance: list[Preference] = []

    def final_scope(cue: str) -> PreferenceScope:
        return PreferenceScope(cue) if cue != "none" else scope

    def money(item: ExtractedMoney | None, label: str) -> int | None:
        if item is None:
            return None
        cents = parse_amount(item.amount_eur, allowed)
        if cents is None:
            questions.append(
                OpenQuestion(
                    question=f"I could not find the {label} amount in your text. "
                    "What number do you mean?",
                    why="I only use numbers you wrote yourself.",
                )
            )
        return cents

    def dropped_loose(label: str) -> None:
        questions.append(
            OpenQuestion(question=f"Do you really want to loosen the {label}?", why=_INJECTION_WHY)
        )

    # allergens (tightening: always allowed)
    seen: set[str] = set()
    for a in out.excluded_allergens:
        name = a.name.strip().lower()
        if name and name not in seen:
            seen.add(name)
            rules.append(
                HardRule(
                    kind=RuleKind.EXCLUDED_ALLERGEN,
                    value=name,
                    scope=final_scope(a.scope_cue),
                    source_text=source,
                )
            )

    # auto-approve limit
    limit = out.auto_approve_limit
    cents = money(limit, "auto-approve limit")
    if cents is not None and limit is not None:
        if cents > DEFAULT_ORDER_LIMIT_CENTS and flagged:
            dropped_loose("auto-approve limit")
        else:
            rules.append(
                HardRule(
                    kind=RuleKind.AUTO_APPROVE_LIMIT_CENTS,
                    value=cents,
                    scope=final_scope(limit.scope_cue),
                    source_text=source,
                )
            )
            if cents > DEFAULT_ORDER_LIMIT_CENTS:
                loosened.append(
                    f"auto-approve limit {_eur(cents)} EUR is above the default "
                    f"{_eur(DEFAULT_ORDER_LIMIT_CENTS)} EUR"
                )

    extra: dict[str, Any] = {}
    cap = money(out.per_line_cap, "per-line cap")
    if cap is not None:
        if cap > DEFAULT_PER_LINE_CAP_CENTS and flagged:
            dropped_loose("per-line cap")
        else:
            extra["per_line_cap_cents"] = cap
            if cap > DEFAULT_PER_LINE_CAP_CENTS:
                loosened.append(
                    f"per-line cap {_eur(cap)} EUR is above the default "
                    f"{_eur(DEFAULT_PER_LINE_CAP_CENTS)} EUR"
                )
    budget = money(out.weekly_budget, "weekly budget")
    if budget is not None:
        if flagged:
            dropped_loose("weekly budget")
        else:
            extra["weekly_budget_cents"] = budget

    # blocklist: only ids that really appear in the text
    wanted = [b.strip() for b in out.blocklist_product_ids if b.strip()]
    block = [b for b in dict.fromkeys(wanted) if b in text]
    if len(block) != len(set(wanted)):
        questions.append(
            OpenQuestion(
                question="Which product ids should never be ordered?",
                why="I only block ids that you wrote in your text.",
            )
        )

    # uncertainty policy
    policy = UncertaintyPolicy.ASK
    stated = out.uncertainty_policy
    if stated == "decline":
        policy = UncertaintyPolicy.DECLINE
    elif stated == "approve":
        if flagged:
            dropped_loose("rule about asking you")
        elif says_do_not_ask(text):
            policy = UncertaintyPolicy.APPROVE
            loosened.append("uncertainty policy 'approve': orders go through without asking you")
        else:
            questions.append(
                OpenQuestion(
                    question="Do you want me to order without asking you when I am unsure?",
                    why="You did not clearly say not to ask, so I will keep asking.",
                )
            )

    # expiry: only an explicit ISO date written in the text
    if out.expires_on:
        written = out.expires_on.strip()
        expires = None
        if written in {m.group(0) for m in _ISO_DATE.finditer(text)}:
            try:
                d = date.fromisoformat(written)
                expires = datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=ZoneInfo(_TZ))
            except (ValueError, KeyError):
                expires = None
        if expires is not None:
            extra["expires_at"] = expires
        else:
            questions.append(
                OpenQuestion(
                    question="Until what date should these rules apply?",
                    why="I could not find a clear date (YYYY-MM-DD).",
                )
            )

    # guidance: soft, never a gate, plus an honest open question
    for g in out.guidance:
        wish = g.text.strip()
        if not wish:
            continue
        guidance.append(Preference(text=wish, scope=final_scope(g.scope_cue)))
        questions.append(
            OpenQuestion(
                question=f'I noted "{wish}" as a wish, but I cannot enforce it automatically '
                "yet. Should I ask you about it on each order?",
                why="No automatic check exists yet for this kind of rule.",
            )
        )

    if flagged:
        questions.append(
            OpenQuestion(
                question="Your text contained instructions aimed at the system. "
                "Please state your own rules in plain words.",
                why=_INJECTION_WHY,
            )
        )

    mandate = Mandate(
        id=mandate_id,
        buyer_id=buyer_id,
        hard_rules=rules,
        uncertainty_policy=policy,
        guidance=guidance,
        open_questions=questions,
        blocklist=block,
        **extra,
    )
    return CompileResult(mandate=mandate, loosened=tuple(loosened), injection_flagged=flagged)
