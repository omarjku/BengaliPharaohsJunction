import pytest
from builders import BUYER, LATER, add, make_store
from helpers_b import ALWAYS, THIS, ctx, item_ids

from trade_profile.models import EventType


def test_this_order_only_for_its_own_order(tmp_path):
    s = make_store(tmp_path)
    m = add(s, scope=THIS, order_id="ord-1")
    assert m.id in item_ids(ctx(s, "ord-1"))
    assert item_ids(ctx(s, "ord-2", now=LATER)) == set()
    assert item_ids(ctx(s, "ord-2")) == set()


def test_close_order_expires_even_for_own_order(tmp_path):
    s = make_store(tmp_path)
    m = add(s, scope=THIS, order_id="ord-1")
    assert s.close_order(BUYER, "ord-1", LATER) == [m.id]
    assert item_ids(ctx(s, "ord-1", now=LATER)) == set()
    assert EventType.EXPIRE in [e.type for e in s.events(BUYER)]


def test_always_persists_until_revoked(tmp_path):
    s = make_store(tmp_path)
    m = add(s, scope=ALWAYS)
    for order in ("ord-1", "ord-2", "ord-99"):
        assert m.id in item_ids(ctx(s, order, now=LATER))
    s.revoke(BUYER, m.id, LATER)
    assert item_ids(ctx(s, "ord-2", now=LATER)) == set()


def test_default_scope_is_this_order(tmp_path):
    s = make_store(tmp_path)
    m = add(s)  # no scope given
    assert m.scope == THIS
    assert item_ids(ctx(s, "ord-other", now=LATER)) == set()


def test_this_order_without_order_id_raises(tmp_path):
    s = make_store(tmp_path)
    with pytest.raises(ValueError):
        add(s, scope=THIS, order_id=None)
    assert s.events(BUYER) == []


def test_promote_needs_human(tmp_path):
    s = make_store(tmp_path)
    m = add(s, scope=THIS, order_id="ord-1")
    before = s.events(BUYER)
    with pytest.raises(PermissionError):
        s.promote_to_always(BUYER, m.id, LATER, by_human=False)
    assert s.events(BUYER) == before
    assert item_ids(ctx(s, "ord-2", now=LATER)) == set()
    assert item_ids(ctx(s, "ord-1", now=LATER)) == {m.id}


def test_promote_by_human_applies_to_later_orders(tmp_path):
    s = make_store(tmp_path)
    m = add(s, scope=THIS, order_id="ord-1")
    p = s.promote_to_always(BUYER, m.id, LATER, by_human=True)
    assert p.scope == ALWAYS and p.order_id is None
    assert p.id in item_ids(ctx(s, "ord-2", now=LATER))
    assert EventType.PROMOTE in [e.type for e in s.events(BUYER)]
