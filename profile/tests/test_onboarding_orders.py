from datetime import timedelta

from builders import BUYER, NOW, OTHER_BUYER, FakePastOrders, add, make_order, make_store
from helpers_b import ALWAYS, ctx

from trade_profile import ONBOARDING_QUESTIONS, MemoryKind, MemorySource


def test_onboarding_stores_always_memories(tmp_path):
    s = make_store(tmp_path)
    mems = s.record_onboarding(
        BUYER,
        {"business_type": "cafe", "allergens": ["peanut", "wheat"], "spend_comfort": 500,
         "bogus_id": "ignored"},
        NOW,
    )  # fmt: skip
    assert all(m.scope == ALWAYS and m.source is MemorySource.ONBOARDING for m in mems)
    assert all(m.order_id is None for m in mems)
    assert sorted(m.kind for m in mems) == sorted(
        [MemoryKind.BUSINESS_TYPE, MemoryKind.ALLERGEN_AVOID, MemoryKind.ALLERGEN_AVOID,
         MemoryKind.SPEND_COMFORT]
    )  # fmt: skip
    assert {m.key for m in mems if m.kind is MemoryKind.ALLERGEN_AVOID} == {"peanut", "wheat"}
    assert "bogus_id" not in str([m.model_dump() for m in mems])
    c = ctx(s, "any-order")
    assert len(c.items) == 4
    answered = {"business_type", "allergens", "spend_comfort"}
    answered_q = {q.question for q in ONBOARDING_QUESTIONS if q.id in answered}
    assert not (set(c.suggested_questions) & answered_q)


def test_unknown_only_answers_store_nothing(tmp_path):
    s = make_store(tmp_path)
    assert s.record_onboarding(BUYER, {"nope": 1}, NOW) == []


def test_recent_orders_newest_first_limited_own_only(tmp_path):
    s = make_store(tmp_path)
    po = FakePastOrders(
        make_order("o1", days_ago=10), make_order("o2", days_ago=2), make_order("o3", days_ago=5),
        make_order("o4", days_ago=1), make_order("o5", days_ago=7), make_order("o6", days_ago=3),
        make_order("x1", buyer=OTHER_BUYER, days_ago=0),
    )  # fmt: skip
    c = ctx(s, past_orders=po)
    assert [o.order_id for o in c.recent_orders] == ["o4", "o2", "o6", "o3", "o5"]
    c2 = ctx(s, past_orders=po, max_recent_orders=2)
    assert [o.order_id for o in c2.recent_orders] == ["o4", "o2"]
    assert all(o.buyer_id == BUYER for o in c.recent_orders)


def test_no_past_orders_gives_empty(tmp_path):
    assert ctx(make_store(tmp_path), past_orders=None).recent_orders == []


def test_long_history_deterministic(tmp_path):
    a, b = make_store(tmp_path / "a"), make_store(tmp_path / "b")

    def put(store, i):
        add(store, key=f"k{i}", kind=MemoryKind.PREFERENCE_NOTE, text=f"note {i}", scope=ALWAYS,
            now=NOW + timedelta(seconds=i), value={"i": i})  # fmt: skip

    for i in range(500):
        put(a, i)
    for i in reversed(range(500)):
        put(b, i)
    now = NOW + timedelta(days=1)
    ca, cb = ctx(a, now=now), ctx(b, now=now)
    assert len(ca.items) == 500
    assert ca.model_dump() == cb.model_dump() == ctx(a, now=now).model_dump()
