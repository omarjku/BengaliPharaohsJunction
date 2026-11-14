# J1/J2 best practices: research (Codex gpt-reserve with web search, Sat 14 Nov ~23:55)

Ask: how to raise Valio J1 (end-to-end demo, 65 in Zoha's report v4) and J2 (user need, 55). Sources are linked per item.

The repo already has the right J1 backbone. The main weakness is proof: the 33-case set is tuned on itself, and the latest real-Gemini acceptance is only documented as 7/12.

1. **Freeze one golden demo path:** photo/text request → parsed cart → fresh quote → held order → judge approval → signed audit. Rehearse exact inputs; no free-form conversation. **Moves:** J1/J3. **Impact:** High. **Effort:** S. Sources: [AngelHack demo structure](https://angelhack.com/blog/10-tips-to-help-you-rock-your-next-hackathon-demo/), [Anthropic agent checkpoints](https://www.anthropic.com/research/building-effective-agents).

2. **Add a visible state rail:** `heard → slots → candidate → quantity conversion → quote → mandate → order/approval → audit`. Show structured outputs and tool results, never hidden chain-of-thought. **Moves:** J1/J5/J2. **Impact:** High. **Effort:** M. Sources: [OpenAI trace grading](https://developers.openai.com/api/docs/guides/trace-grading), [Google trajectory evaluation](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/evaluation-agents).

3. **Make the final cart inspectable:** show original wording, selected SKU, variant, confidence, why it matches, and why the main rejected alternative lost. **Moves:** J2. **Impact:** High. **Effort:** S/M. Sources: [ProductAgent clarification benchmark](https://aclanthology.org/anthology-files/pdf/emnlp/2025.emnlp-industry.25.pdf), [OpenAI evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices).

4. **Use structured slot filling:** product/form, amount, unit, delivery date, diet/allergen, buyer, and purpose. Ask one question only when ambiguity can change the order; otherwise state a visible assumption with an edit action. **Moves:** J2/J3. **Impact:** High. **Effort:** M. Sources: [ProductAgent](https://aclanthology.org/anthology-files/pdf/emnlp/2025.emnlp-industry.25.pdf), [Google human-in-the-loop tool guidance](https://developers.google.com/ml-kit/genai/agent/android/define-tools?hl=en).

5. **Confirm by default for inferred facts:** require confirmation for substitutes, profile-derived choices, pack rounding, or any assumption; retain auto-order only for explicit, high-confidence, policy-safe requests. **Moves:** J2/J3. **Impact:** High. **Effort:** S/M. Sources: [Google HITL guidance](https://developers.google.com/ml-kit/genai/agent/android/define-tools?hl=en), [Anthropic autonomy research](https://www.anthropic.com/research/measuring-agent-autonomy).

6. **Expose quantity reasoning:** requested amount, sales unit, pack count, delivered amount, rounding/overage, and price per requested unit. Add visible cases for `2.5 cartons`, `25 kg`, and large quantities. **Moves:** J2/J4. **Impact:** High. **Effort:** S. Sources: [Baymard product-page UX](https://baymard.com/research-articles/current-state-ecommerce-product-page-ux?r=0), [Baymard product-list UX](https://baymard.com/research-articles/current-state-product-list-and-filtering?trk=article-ssr-frontend-pulse_little-text-block).

7. **Show good/better/best alternatives:** 2–3 same-kind choices with explicit tradeoffs: exact match, cheaper, faster/safer; include allergen and stock evidence. Never offer an unsafe or semantically different substitute. **Moves:** J2/J4. **Impact:** Medium/High. **Effort:** M. Sources: [ProductAgent](https://aclanthology.org/anthology-files/pdf/emnlp/2025.emnlp-industry.25.pdf), [WebMall e-commerce benchmark](https://arxiv.org/abs/2508.13024).

8. **Use history as a labeled default:** show “usual product” or standing-order reuse as `suggested from kitchen history`, never silently substitute it for the current request; preserve all user edits. **Moves:** J2. **Impact:** Medium/High. **Effort:** M. Sources: [ProductAgent memory/clarification design](https://aclanthology.org/anthology-files/pdf/emnlp/2025.emnlp-industry.25.pdf), [Gartner B2B buyer research](https://www.gartner.com/en/newsroom/press-releases/2025-06-25-gartner-sales-survey-finds-61-percent-of-b2b-buyers-prefer-a-rep-free-buying-experience).

9. **Create a frozen J2 eval set:** 30–40 distinct scenarios across exact orders, ambiguity, Finnish/English pairs, pack sizes, standing orders, allergens, substitutions, and delivery constraints. Keep tuned/dev cases separate from held-out cases. **Moves:** J2/J5. **Impact:** High. **Effort:** M. Sources: [OpenAI eval best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices), [Anthropic eval methodology](https://www.anthropic.com/research/demystifying-evals-for-ai-agents).

10. **Run reliability repeats:** execute at least 10 critical cases three times and report task success, first-time-right, correction turns, clarification rate, unsafe auto-orders, and pass^3. Treat 33 tuned cases as exploratory, not generalization proof. **Moves:** J2/J3. **Impact:** High. **Effort:** M. Sources: [τ-bench pass^k](https://arxiv.org/abs/2406.12045), [OpenAI trace grading](https://developers.openai.com/api/docs/guides/trace-grading).

11. **Add a six-case adversarial gate:** coffee milk, missing allergen data, passed cut-off, `999999` stock, duplicate submission, and 25 kg butter correction. Expected result must be “ask/hold/refuse,” never an unsafe order. **Moves:** J2/J3/J4. **Impact:** High. **Effort:** S/M. Sources: [τ-bench policy/state evaluation](https://arxiv.org/abs/2406.12045), [Google trajectory evaluation](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/evaluation-agents).

12. **Prepare an explicit fallback:** warm the service, preload the demo kitchen, keep a screen recording of the same flow, and show a clear “Gemini unavailable → deterministic fallback → no silent confirmation” state. **Moves:** J1/J3. **Impact:** High. **Effort:** S. Sources: [AngelHack demo checklist](https://angelhack.com/blog/10-tips-to-help-you-rock-your-next-hackathon-demo/), [Anthropic agent recovery/checkpoints](https://www.anthropic.com/research/building-effective-agents).

### How to present the J2 number

1. Define success as the exact product/variant, quantity conversion, date, dietary constraints, and safe final state matching the gold case.  
2. Say: “On **N frozen cases**, first-time-right was **X/N**; after one clarification, success was **Y/N**.”  
3. Add “median correction turns,” clarification rate, unsafe auto-orders, and pass^3; do not report only a single accuracy number.  
4. State that the existing 33-case result was tuned on the same set; call it development evidence, not held-out validation.  
5. Show one successful trace and one honest hold/failure beside the number.