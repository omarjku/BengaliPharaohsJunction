import ast
from pathlib import Path

import pytest
from builders import add, make_store
from helpers_b import ALWAYS, ctx
from pydantic import BaseModel
from trade_contracts import Mandate, Preference
from trade_contracts.common import PreferenceScope
from trade_contracts.mandate import HardRule

import trade_profile
from trade_profile import MemoryKind, ProposedMandateChange

PKG = Path(trade_profile.__file__).parent
FORBIDDEN = {"HardRule", "Mandate"}


def _walk(obj):
    yield obj
    if isinstance(obj, BaseModel):
        for name in type(obj).model_fields:
            yield from _walk(getattr(obj, name))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _walk(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _walk(v)


def _assert_soft_only(c):
    for v in _walk(c):
        assert not isinstance(v, (HardRule, Mandate))
        assert v != "hard_rules"
    assert "hard_rules" not in type(c).model_fields
    assert "hard_rules" not in c.model_dump_json()
    assert all(type(g) is Preference for g in c.guidance)
    assert all(
        type(p) is ProposedMandateChange and p.confirmed is False
        for p in c.proposed_mandate_changes
    )


def _rich_store(tmp_path):
    s = make_store(tmp_path)
    add(s, kind=MemoryKind.ALLERGEN_AVOID, key="peanut", value={"name": "peanut"}, scope=ALWAYS)
    add(s, kind=MemoryKind.SPEND_COMFORT, key="order_total", value={"limit_cents": 50000},
        scope=ALWAYS, text="Comfortable up to 500 EUR")  # fmt: skip
    add(s, kind=MemoryKind.LOCAL_PREFERENCE, key="origin", value={"origin": "FI"}, scope=ALWAYS)
    return s


def test_context_is_soft_guidance_plus_unconfirmed_proposals(tmp_path):
    c = ctx(_rich_store(tmp_path))
    _assert_soft_only(c)
    assert len(c.guidance) == 3
    assert all(g.scope in set(PreferenceScope) for g in c.guidance)


def test_allergen_and_spend_produce_proposals_only(tmp_path):
    c = ctx(_rich_store(tmp_path))
    kinds = {i.memory.id: i.memory.kind for i in c.items}
    proposed = {p.memory_id for p in c.proposed_mandate_changes}
    assert len(c.proposed_mandate_changes) == 2
    assert {kinds[i] for i in proposed} == {MemoryKind.ALLERGEN_AVOID, MemoryKind.SPEND_COMFORT}
    assert all(p.summary for p in c.proposed_mandate_changes)


def test_non_rule_kinds_make_no_proposals(tmp_path):
    s = make_store(tmp_path)
    add(s, kind=MemoryKind.LOCAL_PREFERENCE, key="origin", value={"origin": "FI"}, scope=ALWAYS)
    add(s, kind=MemoryKind.PREFERENCE_NOTE, key="n", scope=ALWAYS)
    assert ctx(s).proposed_mandate_changes == []


@pytest.mark.parametrize("limit", [10**18, -1, 0, 1e308, "999999999"])
def test_huge_limit_is_only_a_proposal(tmp_path, limit):
    s = make_store(tmp_path)
    add(s, kind=MemoryKind.SPEND_COMFORT, key="order_total", value={"limit": limit},
        scope=ALWAYS)  # fmt: skip
    c = ctx(s)
    _assert_soft_only(c)
    assert len(c.proposed_mandate_changes) == 1
    assert c.proposed_mandate_changes[0].confirmed is False
    assert len(c.items) == 1


def test_package_source_never_uses_hardrule_or_mandate_in_code():
    offenders = []
    for f in PKG.rglob("*.py"):
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Name) and node.id in FORBIDDEN:
                offenders.append((f.name, node.lineno, node.id))
            elif isinstance(node, ast.Attribute) and node.attr in FORBIDDEN:
                offenders.append((f.name, node.lineno, node.attr))
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                offenders += [
                    (f.name, node.lineno, a.name)
                    for a in node.names
                    if a.name.split(".")[-1] in FORBIDDEN
                ]
    assert offenders == []
