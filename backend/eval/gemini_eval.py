"""Small labelled evaluation of the Gemini Decisions judge the agent uses (agent._judge_one, gemini-decision-1).

Each case: a chef's request, a REAL Valio catalogue product, the question kind the agent asks ("meets": is it the
product asked for; "sub": is it an acceptable substitute), and the correct answer. Run live:

    cd backend && .venv/bin/python -m eval.gemini_eval            # prints the table, writes eval/results.json

Like production (agent.judge_line), a "meets" line whose quantity our resolver can convert is judged on
"meets" (request without amounts) and "qty" (with the resolver's explanation), scored by the weaker answer. "Auto" at threshold t = P(yes) >= t, i.e. the agent would act without asking. Precision of auto = how often an
autonomous yes was right; recall = how many right answers it handled alone. A false auto is the costly error.
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import agent, catalogue, quantity  # noqa: E402

THRESHOLDS = (0.6, 0.7, 0.8, 0.9)
# (request, product_id, kind, correct, why the label)
CASES = [
    # --- clear matches
    ("1000 L lactose-free milk", "464073", "meets", True, "lactose-free whole milk"),
    ("200 L whole milk", "463810", "meets", True, "organic whole milk"),
    ("20 L whipping cream", "464194", "meets", True, "whipping cream 1 l"),
    ("5 kg unsalted butter", "464411", "meets", True, "unsalted butter 500 g"),
    ("6 kg cream cheese for a cheesecake", "462876", "meets", True, "Philadelphia original cream cheese"),
    ("10 kg caster sugar", "460325", "meets", True, "caster sugar 1 kg"),
    ("12 kg reindeer meat for sautéed reindeer", "462959", "meets", True, "reindeer top loin"),
    ("10 kg salmon fillet", "461885", "meets", True, "salmon fillet ~10 kg"),
    ("6 kg lingonberry jam", "460748", "meets", True, "lingonberry jam 6 kg"),
    ("20 L oat drink for vegan guests", "460825", "meets", True, "Oatly organic oat drink, vegan"),
    ("5 L lactose-free coffee milk", "464237", "meets", True, "lactose-free coffee milk 1 l"),
    ("3 kg lactose-free cream cheese", "463200", "meets", True, "Valio Viola lactose free 3.5 kg"),
    # --- traps
    ("1000 L lactose-free milk", "460448", "meets", False, "chocolate milk drink, not milk"),
    ("200 L whole milk", "462921", "meets", False, "semi-skimmed milk drink, not whole milk"),
    ("10 kg sugar for baking", "465354", "meets", False, "500 x 5 g brown sugar sachets, not bulk baking sugar"),
    ("20 L dairy-free milk for a guest with a milk allergy", "464073", "meets", False,
     "lactose-free milk still contains milk protein"),
    ("5 kg unsalted butter", "463437", "meets", False, "salted butter"),
    ("5 kg butter", "464315", "meets", False, "peanut butter"),
    ("10 L cream", "461050", "meets", False, "whisky-cream ice cream"),
    ("12 kg reindeer meat for a stew", "462253", "meets", False, "ready meal with reindeer"),
    ("10 kg salmon fillet", "460608", "meets", False, "salmon-potato casserole"),
    ("gluten-free bread for 40 guests", "461578", "meets", False, "rye bread contains gluten"),
    ("3 kg lactose-free cream cheese", "462876", "meets", False, "regular cream cheese, not lactose-free"),
    ("10 L unsweetened oat drink for cooking", "464226", "meets", False, "chocolate oat drink in 2.5 dl packs"),
    ("5 L coffee milk", "465761", "meets", False, "Starbucks skinny latte drink"),
    # --- substitutes (the requested product can't be delivered)
    ("1000 L lactose-free milk", "462921", "sub", True, "lactose-free milk drink: fine for a lactose-free need"),
    ("20 L whipping cream", "463366", "sub", True, "38 % whipping cream 10 l"),
    ("20 L dairy-free milk for a guest with a milk allergy", "460825", "sub", True, "oat drink is milk-free"),
    ("100 L lactose-free whole milk", "463810", "sub", False, "regular whole milk is not lactose-free"),
    ("10 kg caster sugar", "460270", "sub", False, "jam sugar contains pectin"),
]


async def run() -> list[dict]:
    catalogue.load()
    out = []
    for req, pid, kind, correct, why in CASES:
        p = catalogue.get(pid)
        # Exactly what production asks: for a line it may order, "meets" + "qty" with our resolver's explanation in
        # the input, thresholded on the weaker answer; for a substitute, "sub".
        [item] = agent.fallback_parse(req)[:1] or [{"amount": None, "unit": None}]
        qty = quantity.resolve(p, item["amount"], item["unit"]) if item["amount"] and item["unit"] else None
        if kind == "meets" and qty and qty["quantity"] is not None:
            conf, reason, _ = await agent.judge_line(req, p, qty["explanation"])
        else:
            conf, reason, _ = await agent._judge_one(req, p, [kind])
        out.append({"request": req, "product_id": pid, "product": agent._name(p), "kind": kind, "correct": correct,
                    "label_why": why, "p_yes": conf, "judge": reason})
    return out


def score(rows: list[dict]) -> dict:
    ok = [r for r in rows if r["p_yes"] is not None]
    acc = sum((r["p_yes"] >= 0.5) == r["correct"] for r in ok) / len(ok)
    table = []
    for t in THRESHOLDS:
        auto = [r for r in ok if r["p_yes"] >= t]
        yes = [r for r in ok if r["correct"]]
        tp = sum(r["correct"] for r in auto)
        table.append({"threshold": t, "auto": len(auto), "false_auto": len(auto) - tp,
                      "precision": tp / len(auto) if auto else None, "recall": tp / len(yes) if yes else None})
    return {"cases": len(rows), "answered": len(ok), "accuracy_at_0.5": acc, "auto": table}


def main() -> None:
    rows = asyncio.run(run())
    s = score(rows)
    Path(__file__).with_name("results.json").write_text(json.dumps({"summary": s, "rows": rows}, indent=1,
                                                                   ensure_ascii=False))
    for r in rows:
        mark = "ok " if r["p_yes"] is not None and (r["p_yes"] >= 0.5) == r["correct"] else "MISS"
        print(f"{mark} {r['kind']:5} {'yes' if r['correct'] else 'no ':3} p={r['p_yes'] if r['p_yes'] is None else round(r['p_yes'], 2)!s:5}"
              f" {r['request'][:42]:42} → {r['product'][:48]}")
    print(f"\naccuracy (P(yes) >= 0.5 vs label): {s['accuracy_at_0.5']:.0%} of {s['answered']}/{s['cases']}")
    print("| threshold | auto | false auto | precision | recall |\n|---|---|---|---|---|")
    for x in s["auto"]:
        prec = "-" if x["precision"] is None else f"{x['precision']:.0%}"
        print(f"| {x['threshold']} | {x['auto']} | {x['false_auto']} | {prec} | {x['recall']:.0%} |")


if __name__ == "__main__":
    main()
