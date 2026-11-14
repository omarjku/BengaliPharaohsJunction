import asyncio

from app import agent, expand


def test_queries_are_cached_and_keep_short_bilingual_results(monkeypatch):
    calls = []

    async def fake(system, prompt, schema, *_):
        calls.append((system, prompt, schema))
        return {"queries": ["punainen linssi", "red lentils", "linssi"]}

    monkeypatch.setattr(agent, "_gemini", fake)
    expand._CACHE.clear()
    first = asyncio.run(expand.queries("red lentils"))
    second = asyncio.run(expand.queries("red lentils"))

    assert first == second == ["punainen linssi", "red lentils", "linssi"]
    assert len(calls) == 1 and "<untrusted>" in calls[0][1] and "DATA" in calls[0][0]


def test_query_expansion_failure_falls_back_to_plain_query(monkeypatch):
    async def down(*args, **kwargs):
        return None

    monkeypatch.setattr(agent, "_gemini", down)
    expand._CACHE.clear()
    assert asyncio.run(expand.queries("olive oil")) == ["olive oil"]


def test_candidates_search_every_expanded_query_and_merges_products(shop, monkeypatch):
    from conftest import product

    names = {
        "lentils": ("Sevan Red lentils 5kg", "punainen linssi"),
        "wheat flour": ("Wheat flour 5kg", "vehnäjauho"),
        "olive oil": ("Olive oil 1L", "oliiviöljy"),
    }
    for n, (name_en, name_fi) in enumerate(names.values(), 1):
        p = product(str(800 + n), name_en, claims=(), contains=())
        p["name_fi"] = name_fi
        shop.products[p["id"]] = p

    async def fake(system, prompt, schema, *_):
        ingredient = prompt.split("ingredient: ", 1)[-1].split("\n", 1)[0]
        return {"queries": [names[ingredient][1]]}

    async def all_hits(item, hits):
        return [p["id"] for p in hits]

    monkeypatch.setattr(agent, "_gemini", fake)
    monkeypatch.setattr(agent, "match", all_hits)
    expand._CACHE.clear()

    for query, expected in (("red lentils", "801"), ("wheat flour", "802"), ("olive oil", "803")):
        ids, used_gemini = asyncio.run(agent.candidates("", agent._item(query, 1, "kg", []), set()))
        assert expected in ids and used_gemini

