from datetime import timedelta

from builders import LATER, NOW, add, make_store
from helpers_b import ALWAYS, THIS, ctx, item_ids


def test_this_order_beats_always(tmp_path):
    s = make_store(tmp_path)
    a = add(s, scope=ALWAYS, value={"name": "wheat", "v": "strict"})
    t = add(s, scope=THIS, order_id="ord-1", value={"name": "wheat", "v": "relaxed"}, now=LATER)
    c = ctx(s, "ord-1", now=LATER)
    assert item_ids(c) == {t.id}
    assert len(c.overridden) == 1
    o = c.overridden[0]
    assert (o.memory_id, o.by_memory_id) == (a.id, t.id)
    assert "this_order" in o.reason and "always" in o.reason
    used = c.items[0].used_because.lower()
    assert "overrid" in used or "instead" in used or "beats" in used
    # another order: the always memory applies again, no override
    c2 = ctx(s, "ord-2", now=LATER)
    assert item_ids(c2) == {a.id} and c2.overridden == []


def test_same_scope_newer_wins(tmp_path):
    s = make_store(tmp_path)
    old = add(s, scope=ALWAYS, value={"name": "x", "v": 1}, now=NOW)
    new = add(s, scope=ALWAYS, value={"name": "x", "v": 2}, now=NOW + timedelta(hours=1))
    c = ctx(s, "ord-1", now=LATER)
    assert item_ids(c) == {new.id}
    assert [(o.memory_id, o.by_memory_id) for o in c.overridden] == [(old.id, new.id)]


def test_identical_values_not_a_conflict(tmp_path):
    s = make_store(tmp_path)
    add(s, scope=ALWAYS, value={"name": "wheat"})
    add(s, scope=THIS, order_id="ord-1", value={"name": "wheat"})
    c = ctx(s, "ord-1", now=LATER)
    assert c.overridden == []
    assert len(c.items) >= 1


def test_different_keys_not_a_conflict(tmp_path):
    s = make_store(tmp_path)
    a = add(s, key="wheat", scope=ALWAYS)
    b = add(s, key="milk", scope=ALWAYS)
    c = ctx(s, "ord-1")
    assert item_ids(c) == {a.id, b.id} and c.overridden == []
