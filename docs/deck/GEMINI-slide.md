# Gemini slide text (paste into docs/DECK.md at the Gemini slide; not yet pasted)

## Title
Gemini Decisions confidence on 33 labelled cases

Image: docs/deck/assets/gemini-distribution.png (source SVG beside it)

## Table
| Threshold (P(yes) >= t) | Handled alone | Wrong handled alone | Recall (right handled alone) |
|---|---|---|---|
| 0.60 | 15 | 0 | 15/15 = 100% |
| 0.70 | 14 | 0 | 14/15 = 93% |
| 0.80 | 11 | 0 | 11/15 = 73% |
| 0.90 | 6 | 0 | 6/15 = 40% |

## Caption
n = 33 (28 'is it the product' + 5 'acceptable substitute'). Thresholds were tuned on this same set, and 0.60 also had 0 wrong, so this shows separation, not proof of calibration. On these cases the highest wrong score is 0.26 and the lowest right score is 0.67, with no case in between.

## Speaker sentences
1. Each mark is one test case: a red diamond is a wrong product, a green circle a right one.
2. Every wrong product scored 0.26 or lower and every right one 0.67 or higher, and a 0.70 line handles 14 of 15 right products alone with 0 wrong ones.
3. We also tuned on these cases, and 0.60 would have had 0 wrong too, so this shows separation, not proof of calibration.
