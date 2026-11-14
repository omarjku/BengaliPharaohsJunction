"""Gemini Decisions score distribution: SVG dot plot + threshold table from backend/eval/results.json.
Stdlib only. Run from repo root: python scripts/make_dist.py"""
import json, math, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
rows = json.load(open(os.path.join(ROOT, "backend/eval/results.json"), encoding="utf-8"))["rows"]
W, H, L, R, T, B = 1600, 560, 70, 60, 130, 90
X = lambda p: L + (W - L - R) * p
GOOD, BAD, INK, MUTE, LINE = "#1e7a3c", "#b3261e", "#1c1f23", "#5d6670", "#e7e9ec"
RAD, CY = 10, (T + H - B) / 2 + 10
# beeswarm: score order, pick the offset closest to the centre that does not overlap
placed = []
for r in sorted(rows, key=lambda r: r["p_yes"]):
    x = X(r["p_yes"])
    cands = [CY]
    for k in range(1, 40):
        cands += [CY + k * 12, CY - k * 12]
    y = next(c for c in cands if all(math.hypot(x - px, c - py) >= 2 * RAD + 4 for px, py, _ in placed))
    placed.append((x, y, r["correct"]))
o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="Segoe UI,Arial,sans-serif">',
     f'<rect width="{W}" height="{H}" fill="#fff"/>',
     f'<text x="{L}" y="48" font-size="32" font-weight="700" fill="{INK}">Gemini Decisions confidence on 33 labelled cases</text>']
axis_y = H - B
for t in range(11):
    x = X(t / 10)
    o.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{T-10}" y2="{axis_y}" stroke="{LINE}"/>'
             f'<text x="{x:.1f}" y="{axis_y+30}" font-size="24" fill="{MUTE}" text-anchor="middle">{t/10:.1f}</text>')
o.append(f'<line x1="{L}" x2="{W-R}" y1="{axis_y}" y2="{axis_y}" stroke="{MUTE}" stroke-width="2"/>')
o.append(f'<text x="{X(.5):.1f}" y="{H-14}" font-size="24" fill="{MUTE}" text-anchor="middle">P(yes): Gemini probability that the product is what was asked for</text>')
o.append(f'<line x1="{X(.7):.1f}" x2="{X(.7):.1f}" y1="{T-30}" y2="{axis_y}" stroke="{INK}" stroke-width="4" stroke-dasharray="10 6"/>'
         f'<text x="{X(.7)+12:.1f}" y="{T-14}" font-size="26" font-weight="700" fill="{INK}">0.70 line: at or above, ordered alone</text>')
for x, y, ok in placed:
    if ok:
        o.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{RAD}" fill="{GOOD}" stroke="#fff" stroke-width="2"/>')
    else:
        d = RAD + 3
        o.append(f'<polygon points="{x:.1f},{y-d:.1f} {x+d:.1f},{y:.1f} {x:.1f},{y+d:.1f} {x-d:.1f},{y:.1f}" fill="{BAD}" stroke="#fff" stroke-width="2"/>')
ly = 44
o.append(f'<circle cx="{L+760}" cy="{ly}" r="{RAD}" fill="{GOOD}"/><text x="{L+782}" y="{ly+8}" font-size="24" fill="{INK}">right product (circle)</text>')
o.append(f'<polygon points="{L+1060},{ly-15} {L+1075},{ly} {L+1060},{ly+15} {L+1045},{ly}" fill="{BAD}"/><text x="{L+1090}" y="{ly+8}" font-size="24" fill="{INK}">wrong product (diamond)</text>')
o.append("</svg>")
os.makedirs(os.path.join(ROOT, "docs/deck/assets"), exist_ok=True)
open(os.path.join(ROOT, "docs/deck/assets/gemini-distribution.svg"), "w", encoding="utf-8").write("\n".join(o))

right = [r for r in rows if r["correct"]]; wrong = [r for r in rows if not r["correct"]]
hw = max(r["p_yes"] for r in wrong); lr = min(r["p_yes"] for r in right)
n_meets = sum(r["kind"] == "meets" for r in rows); n_sub = len(rows) - n_meets
tab = ["| Threshold (P(yes) >= t) | Handled alone | Wrong handled alone | Recall (right handled alone) |", "|---|---|---|---|"]
for t in (0.6, 0.7, 0.8, 0.9):
    a = [r for r in rows if r["p_yes"] >= t]; w = sum(not r["correct"] for r in a); ok = len(a) - w
    tab.append(f"| {t:.2f} | {len(a)} | {w} | {ok}/{len(right)} = {100*ok/len(right):.0f}% |")
table = "\n".join(tab)
a70 = sum(r["p_yes"] >= 0.7 for r in rows)
print(f"n={len(rows)} right={len(right)} wrong={len(wrong)} meets={n_meets} sub={n_sub}\nhighest wrong={hw:.3f} lowest right={lr:.3f}\n{table}")
md = f"""# Gemini slide text (paste into docs/DECK.md at the Gemini slide; not yet pasted)

## Title
Gemini Decisions confidence on {len(rows)} labelled cases

Image: docs/deck/assets/gemini-distribution.png (source SVG beside it)

## Table
{table}

## Caption
n = {len(rows)} ({n_meets} 'is it the product' + {n_sub} 'acceptable substitute'). Thresholds were tuned on this same set, and 0.60 also had 0 wrong, so this shows separation, not proof of calibration. On these cases the highest wrong score is {hw:.2f} and the lowest right score is {lr:.2f}, with no case in between.

## Speaker sentences
1. Each mark is one test case: a red diamond is a wrong product, a green circle a right one.
2. Every wrong product scored {hw:.2f} or lower and every right one {lr:.2f} or higher, and a 0.70 line handles {a70} of {len(right)} right products alone with 0 wrong ones.
3. We also tuned on these cases, and 0.60 would have had 0 wrong too, so this shows separation, not proof of calibration.
"""
open(os.path.join(ROOT, "docs/deck/GEMINI-slide.md"), "w", encoding="utf-8").write(md)
