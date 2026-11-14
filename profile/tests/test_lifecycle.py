from datetime import timedelta

import pytest
from builders import BUYER, NOW, add, make_store
from helpers_b import ALWAYS, ctx, item_ids

from trade_profile import ONBOARDING_QUESTIONS, log_path
from trade_profile.models import EventType


def test_revoked_never_used(tmp_path):
    s = make_store(tmp_path)
    m = add(s, scope=ALWAYS)
    s.revoke(BUYER, m.id, NOW)
    assert item_ids(ctx(s)) == set()
    assert EventType.REVOKE in [e.type for e in s.events(BUYER)]


def test_revoke_unknown_raises(tmp_path):
    s = make_store(tmp_path)
    with pytest.raises(KeyError):
        s.revoke(BUYER, "mem_nope", NOW)


def test_duplicate_add_is_noop(tmp_path):
    s = make_store(tmp_path)
    a = add(s, scope=ALWAYS)
    b = add(s, scope=ALWAYS)
    assert a.id == b.id
    assert [e.type for e in s.events(BUYER)].count(EventType.ADD) == 1


def test_memory_created_after_now_ignored(tmp_path):
    s = make_store(tmp_path)
    add(s, scope=ALWAYS, now=NOW + timedelta(days=5))
    assert item_ids(ctx(s, now=NOW)) == set()


def test_forget_memory_erases_content_keeps_tombstone(tmp_path):
    s = make_store(tmp_path)
    m = add(s, scope=ALWAYS, text="SECRETTEXT-zq", value={"name": "SECRETVAL-zq"})
    s.forget_memory(BUYER, m.id, NOW)
    raw = log_path(tmp_path, BUYER).read_bytes()
    assert b"SECRETTEXT-zq" not in raw and b"SECRETVAL-zq" not in raw
    assert m.id.encode() in raw
    assert EventType.FORGET in [e.type for e in s.events(BUYER)]
    assert item_ids(ctx(s)) == set()


def test_forget_profile_deletes_file(tmp_path):
    s = make_store(tmp_path)
    add(s, scope=ALWAYS)
    s.forget_profile(BUYER)
    assert not log_path(tmp_path, BUYER).exists()
    c = ctx(s)
    assert c.items == [] and c.guidance == []


def test_empty_profile_suggests_all_onboarding_questions(tmp_path):
    c = ctx(make_store(tmp_path))
    assert c.items == [] and c.overridden == [] and c.proposed_mandate_changes == []
    assert len(ONBOARDING_QUESTIONS) == 5
    for q in ONBOARDING_QUESTIONS:
        assert q.question in c.suggested_questions
    assert len(c.suggested_questions) == 5
