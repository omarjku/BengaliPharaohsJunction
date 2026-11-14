import json

from builders import BUYER, OTHER_BUYER, add, make_store
from helpers_b import ALWAYS, THIS, ctx, item_ids

from trade_profile import log_path


def test_other_buyers_memories_never_returned(tmp_path):
    s = make_store(tmp_path)
    mine = add(s, buyer=BUYER, scope=THIS, order_id="ord-1")
    theirs = add(s, buyer=OTHER_BUYER, key="milk", scope=THIS, order_id="ord-1")
    add(s, buyer=OTHER_BUYER, key="soy", scope=ALWAYS)
    c = ctx(s, "ord-1", buyer=BUYER)
    assert item_ids(c) == {mine.id}
    assert theirs.id not in c.model_dump_json()
    assert "soy" not in c.model_dump_json()


def test_hostile_buyer_id_stays_in_root(tmp_path):
    root = tmp_path / "store"
    root.mkdir()
    s = make_store(root)
    for hostile in ("../evil", "..\\..\\evil2", "a/b"):
        add(s, buyer=hostile, scope=ALWAYS)
    assert [p.name for p in tmp_path.iterdir()] == ["store"]
    for p in root.rglob("*"):
        assert p.resolve().is_relative_to(root.resolve())
    assert len(list(root.glob("*.jsonl"))) == 3
    assert log_path(root, "../evil").resolve().parent == root.resolve()


def test_only_model_fields_are_stored(tmp_path):
    s = make_store(tmp_path)
    add(s, scope=ALWAYS, text="No wheat", value={"name": "wheat"})
    lines = log_path(tmp_path, BUYER).read_text(encoding="utf-8").splitlines()
    ev_keys = {"type", "buyer_id", "at", "memory", "memory_id", "order_id", "by_human"}
    mem_keys = {"id", "buyer_id", "kind", "key", "text", "value", "scope", "source",
                "created_at", "order_id"}  # fmt: skip
    assert lines
    for ln in lines:
        d = json.loads(ln)
        assert set(d) <= ev_keys
        if d.get("memory"):
            assert set(d["memory"]) <= mem_keys
    blob = "\n".join(lines).lower()
    for bad in ("sk-", "api_key", "apikey", "bearer ", "secret", "password"):
        assert bad not in blob
