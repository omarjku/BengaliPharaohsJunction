# Deck notes for Zoha (from Omar, Sun 15 Nov ~06:15)

Deck: "Front Door: pitch deck (base structure)", Google Slides, Zoha's account.
How to use this file: paste section 5 (the Gemini prompt) into Gemini in Google Slides, then polish by hand.
All numbers below were checked against the repo and the live API at 06:10. Do not round them up.

## 1. Rewrite the "next steps" slide (now: "Every assumption is written down")

**Problem:** the only forward-looking line is "Next: Postgres, per-agent identity, Valio's order endpoint, Peppol."
Valio scores J5 (15%) on "a credible view of next development steps". Four nouns are not a plan.
Keep the Real / Assumed column (it is good), but make it the left half. The right half becomes a path to production.

**New title:** "From challenge mock to Valio's real door"

**Left half: what is real today vs. assumed** (keep, tighten)
- Real: live quotes from Valio's challenge mock, the full 17,546-product catalogue, Gemini, Ed25519 signing, MCP, OpenAPI 3.1.
- Assumed: cut-off times, delivery days, order endpoint (the mock has none), purchase history (simulated).
- Found in Valio's data: 8,110 of 17,546 products (46%) have an empty allergen record. Front Door treats "missing" as "unknown" and asks a human. Fixing this data is Valio's single biggest safety win.

**Right half: three steps, each with what we need from Valio**
1. **Pilot (first 3 months): 3 kitchens, one real door.**
   Swap the mock for Valio's order endpoint behind the same OpenAPI contract. Chefs approve in the Valio Aimo webshop they already use, not a new app.
   Measure: manual corrections per order, minutes per order, unsafe auto-orders (target 0).
   *Need from Valio:* an order-endpoint sandbox, real cut-off and delivery-day data, 3 pilot kitchens.
2. **Open the door to every agent.**
   Any buyer agent (Gemini, Claude, ChatGPT, a kitchen's own system) connects over MCP or OpenAPI with its own key and its own mandate. Per-agent identity, mandates as signed credentials, audit retained for disputes.
   *Need:* Valio's identity provider for buyer accounts.
3. **Two-way trade on open standards.**
   Orders and invoices as Peppol messages (the EU e-procurement standard). Valio's own selling agent can offer seasonal products through the same door, and standing orders get drift alerts before they renew. Both are scenarios in Valio's brief.

**Footer line:** "The contract, schemas and mandate format are MIT and published today, so Valio can run the pilot without us."

## 2. Gemini slide (now: "Gemini measures doubt. The mandate controls permission.")

The Gemini judges ask four things: the problem, how Gemini is integrated, what is innovative, why Gemini is essential.
Answer each in one line on the slide:
- **Problem:** an agent that guesses wrong spends a kitchen's money. The hard part is knowing when not to act.
- **How it's integrated (one brain, four Gemini surfaces):**
  - `gemini-4-hydrogen` with function calling is the chat agent. It drives our tools (search, propose, change, check assumptions); it never touches money.
  - `gemini-decision-1` (Decisions API) returns a calibrated yes-probability for each assumption, batched up to 40 questions per call.
  - Vision reads a handwritten Finnish list, and treats instructions planted on the photo as data.
  - `gemini-3.8-live` Talk uses the same tools, and every spoken order waits for a tap.
- **Innovative:** the Decisions score is the autonomy switch. Above the kitchen's threshold (0.70) the agent acts alone; below it, it asks the chef. Confidence can ask; it cannot grant permission.
- **Why Gemini is essential:** calibrated probabilities (not a chatty "I'm sure"), handwriting in Finnish, and live voice, all from one API with the same tools.
- **Numbers (keep these exact):** 0 wrong automatic orders at 0.70 on 33 labelled cases (tuned on this set); 14/15 right lines handled alone; chat agent 105/164 edge cases (64%), with **0 unsafe auto-orders in all 164, including 10 injection attempts**. Voice: first audio about 1.2 s (dev measurement).
- **Remove** the "VERIFY VOICE ON PHONE" note: Omar tested Talk on his phone on Sun 03:07.
- Keep the gemini-distribution.png chart (coffee milk 0.115 vs lactose-free milk 0.897). It is the best visual in the deck.

## 3. Codex slide (now: "Codex built it. Claude ran the room.")

Codex judges look for meaningful use in building, iterating and shipping something ambitious in 48 h.
- **Fix the number:** 29 is stale. **42 commits on main now say "Built by Codex"** (checked with `git log --grep`). That answers your 24-vs-29 question.
- **Show the loop, not just a list:** each Codex worker got its own git worktree and looped against real Gemini (edit, run, measure, fix, add a regression test) until the tests passed. Claude briefed, reviewed and ran the test gate. Up to 5 Codex workers ran in parallel (the overnight audit).
- **Show Codex as an attacker too:** Codex reviews found real bugs we shipped fixes for, for example "a free-from milk cleared a peanut ban" (CRITICAL, fixed) and "order all available used the wrong unit".
- **One proof line:** 787 automated tests pass; every Codex run is logged in docs/CODEX.md with its model, ask, result and commit.
- Models used: gpt-reserve (building), gpt-5.6-terra at ultra effort (adversarial reviews).

## 4. CRACI slide (now: "Which build signed your order?", marked "ONLY IF CRACI LIVE")

**It is live: remove the "ONLY IF" label.** CRACI judges score technical depth (50%) and creative use of SBOMs, AI fixes, provenance, network traces and the API (50%).
- **Hook:** "Every order knows which build signed it."
- **What happens:** all 7 CI jobs run on CRACI runners. The deployed app calls the CRACI API for its own build: the CycloneDX SBOM and network trace of each job. It publishes them at `/.well-known/front-door-build.json`, and the signing key and every signed order point to that build. A tampered or unknown build is visible to the buyer and to Valio.
- **Live numbers (06:10):** status ok; 351 components (170 pip + 181 npm); 17 network destinations seen during the build; SBOM SHA-256 published; CRACI reports 7 HIGH, 0 CRITICAL.
- **Self-defending rule (honest wording):** "The door can refuse to auto-order when its own build carries a blocking vulnerability. The rule is built and tested; for the demo it is switched off, because CRACI reports 7 HIGH that our own scans do not show, and we are tracing them with the CRACI team." Only say "tracing them with the CRACI team" if Omar actually asks at the booth this morning.
- **Story line:** "CRACI found vulnerabilities in our build at midnight; Codex upgraded FastAPI, Starlette, cryptography and minimatch the same night."
- Use the screenshot of the live JSON (status ok) as the image.

## 5. Gemini prompt to paste into Google Slides

```
Update this deck. Keep the existing palette, fonts and layout style. Keep every number exactly as written below.

1) Retitle the slide "Every assumption is written down" to "From challenge mock to Valio's real door". Make it two columns.
Left column, "Today": Real: live quotes from Valio's challenge mock, the full 17,546-product catalogue, Gemini, Ed25519 signing, MCP, OpenAPI 3.1. Assumed: cut-off times, delivery days, the order endpoint, purchase history. Found: 46% of Valio products (8,110 of 17,546) have no allergen record; Front Door treats missing as unknown and asks a human.
Right column, "Next", three numbered steps:
1. Pilot, 3 kitchens: swap the mock for Valio's order endpoint behind the same OpenAPI contract; chefs approve in the webshop they already use; measure corrections per order and time per order, 0 unsafe auto-orders. Need: an order sandbox, real cut-off data, 3 pilot kitchens.
2. Every agent, one door: Gemini, Claude, ChatGPT or a kitchen system connects over MCP or OpenAPI with its own key and mandate; mandates as signed credentials; audit kept for disputes.
3. Two-way trade on open standards: orders and invoices as Peppol messages; Valio's own selling agent offers seasonal products through the same door; standing orders get drift alerts.
Footer: "The contract, schemas and mandate format are MIT and published today."

2) Gemini slide: add four short labelled lines: Problem: an agent that guesses wrong spends a kitchen's money. Integrated: Gemini 4 Hydrogen function calling drives the tools; the Decisions API (gemini-decision-1) scores every assumption, up to 40 per call; vision reads a handwritten Finnish list; Gemini Live voice uses the same tools and every spoken order waits for a tap. Innovative: the Decisions score is the autonomy switch: above 0.70 the agent acts, below it asks the chef. Essential: calibrated probabilities, Finnish handwriting and live voice from one API. Stats: 0 wrong automatic orders at 0.70 on 33 labelled cases; 14/15 right lines handled alone; 0 unsafe auto-orders in 164 chat tests including 10 injection attempts. Delete the note "VERIFY VOICE ON PHONE".

3) Codex slide: change 29 to 42 ("42 commits on main say Built by Codex"). Add: "Parallel Codex workers, each in its own git worktree, looping against real Gemini until the tests pass. Codex also attacked our code: its reviews found a peanut-ban bypass, fixed the same night. 787 automated tests pass. Every run logged in docs/CODEX.md."

4) CRACI slide: delete the "ONLY IF CRACI LIVE" label. Title: "Every order knows which build signed it". Add: "All 7 CI jobs run on CRACI. The live app pulls its own CycloneDX SBOM and network trace from the CRACI API and publishes them at /.well-known/front-door-build.json; the signing key and every signed order point to that build. Live: 351 components, 17 network destinations, SBOM hash published. CRACI found vulnerabilities at midnight; we upgraded FastAPI, Starlette, cryptography and minimatch the same night. Built in: the door can refuse to auto-order when its own build carries a blocking vulnerability."
```

## 6. Smaller fixes
- Slide 1 subtitle says "Team BengaliPharaohs": check it matches the team name on the Junction platform.
- Every slide footer: keep "Valio challenge mock, no real orders or payments".
- Last slide: the QR "Your own test kitchen, 24 h. Try to trick it." is great for peer review; keep it.
