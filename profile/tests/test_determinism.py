from datetime import timedelta

from builders import BUYER, LATER, NOW, add, make_store
from helpers_b import ALWAYS, THIS, ctx

from trade_profile import MemoryKind, memory_id_for


def _history(store, order):
    steps = {
        "a": {"key": "wheat", "scope": ALWAYS, "now": NOW},
        "b": {"kind": MemoryKind.SPEND_COMFORT, "key": "order_total", "value": {"limit": 5},
              "scope": ALWAYS, "now": NOW + timedelta(hours=1)},
        "c": {"key": "wheat", "scope": THIS, "order_id": "ord-1",
              "value": {"name": "wheat", "x": 1}, "now": NOW + timedelta(hours=2)},
        "d": {"kind": MemoryKind.LOCAL_PREFERENCE, "key": "origin", "value": {"origin": "FI"},
              "scope": ALWAYS, "now": NOW + timedelta(hours=3)},
    }  # fmt: skip
    for k in order:
        add(store, **steps[k])


def test_repeat_calls_equal(tmp_path):
    s = make_store(tmp_path)
    _history(s, "abcd")
    first = ctx(s, now=LATER).model_dump()
    assert all(ctx(s, now=LATER).model_dump() == first for _ in range(3))


def test_insertion_order_does_not_matter(tmp_path):
    a, b = make_store(tmp_path / "a"), make_store(tmp_path / "b")
    _history(a, "abcd")
    _history(b, "dcba")
    assert ctx(a, now=LATER).model_dump() == ctx(b, now=LATER).model_dump()


def test_memory_ids_content_based(tmp_path):
    a, b = make_store(tmp_path / "a"), make_store(tmp_path / "b")
    m1 = add(a, scope=ALWAYS, now=NOW)
    m2 = add(b, scope=ALWAYS, now=LATER)  # different time, same content
    assert m1.id == m2.id
    assert m1.id == memory_id_for(BUYER, m1.kind, m1.key, m1.value, m1.scope, m1.order_id)
    assert add(a, key="milk", scope=ALWAYS).id != m1.id
