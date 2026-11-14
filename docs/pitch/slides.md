# Front Door: slides v2 (7 slides, plus 1 if CRACI is live)

These are a base for the team to polish. Each slide carries **one message** and the **evidence** under it, nothing
else.

**Style:**
- the existing deck's white field, graphite text, blue `#0B5CAD`, amber for review, green for confirmed;
- the ticket-and-stamp motif, used sparingly;
- real screenshots in phone frames.

**Truth tags:**
- **[VERIFY VOICE ON PHONE]**
- **[ONLY IF CRACI LIVE]**
- **[OPTION]**

---

### 1. Front Door
- **Message:** Agents knock. The door checks. The chef decides.
- **Evidence:** Valio's example request, *"1,000 litres of lactose-free milk by Monday"*, handwritten in Finnish on a
  real list, with a planted note for the AI.
- **Visual:** that list, full bleed (`docs/demo-images/handwritten-list-planted.jpg`), with a white title band and a
  thin blue vertical "door" line cutting through the sticky note.
- **Notes:** The team, the line, then hand the printed list to the judge. No market statistics.

### 2. The agent proposes. Valio's door decides. Only a human approves.
- **Evidence:**
  - a Gemini agent with tools over a deterministic engine: 17,546 Valio products, live quotes, units, allergen
    evidence;
  - the mandate is stored at Valio's side, and every decision is Ed25519-signed;
  - any agent can use the door: ours, Claude over MCP, or anyone over OpenAPI 3.1.
- **Visual:** the last frame of the video's architecture animation (agents knocking → one blue door with checks →
  ORDERED / HELD / NOT ORDERED → signed stub).
- **Notes:** Under 15 seconds. "Our agent is one client; the door is the product."

### 3. One photo, end to end
- **Message:** Read → scored → priced → held → approved → signed.
- **Evidence:**
  - **€1,560 > €1,500**: the milk line alone, over the kitchen's per-order limit;
  - an agent key gets 401 on approve, and can't cancel a confirmed order (#115);
  - one real take: real Gemini, real calls to Valio's challenge mock.
- **Visual:** a strip of six phone screens from the video's live take, joined by one sliding ticket: photo read
  (note flagged) · Decisions score · live quote · HELD · the approve tap · "Signed by the front door ✓". The
  inequality runs large across the top.
- **Notes:** This is J1 (30%) and J3 (20%) on one slide. Then: "You'll do the tap yourself."

### 4. Gemini measures doubt. The mandate controls permission.
- **Evidence:**
  - 33 labelled cases with real Valio products: **0 wrong automatic orders at 0.70**, and 14 of 15 right lines
    handled alone. *We tuned on this set; a held-out test is next.*
  - Coffee milk ("cheapest") scores **0.115**; lactose-free milk **0.897**.
  - Decisions answers are repeatable (6 of 6 identical) and take about 0.5 s.
  - **[VERIFY VOICE ON PHONE]** Gemini Live uses the same tools: a spoken order is held for a tap, with first audio
    in 1.17 s (a dev measurement).
- **Visual:** the score-distribution chart (`docs/deck/assets/gemini-distribution.png`) with the dashed 0.70 line,
  coffee milk and lactose-free milk called out, and an amber arrow under the line: "ask the chef". Three chips:
  *Reads* · *Scores* · *Talks* (one API family).
- **Notes:**
  - Coffee milk once scored 0.72 (from our notes); our QA caught it, not the calibration.
  - Without Gemini, the agent asks: less autonomy, same safety (on/off test, 5 requests).

### 5. Every trap becomes a question, and every assumption is written down
- **Evidence:**
  - J4: cut-off passed despite "available Monday" · stock 999999 = unknown · missing allergen data → ask ·
    same-kind, allergen-safe substitutes · instructions in photos are ignored.
  - J5: OpenAPI 3.1 · JSON Schemas · MCP · Ed25519 keys at `/.well-known` · MIT · CI on CRACI.
  - **Measured, honestly:** 33 labelled cases (tuned set) · 14 of 22 real-Gemini acceptance flows on the engine path
    (`docs/testing/acceptance-integration-118a63b.md`). **[OPTION]** Keep the 14/22 on the slide, or move it to the
    notes.
  - **Real / Assumed / Next:**
    - Real: fresh quotes from the Valio challenge mock, the full catalogue, Gemini, signing, MCP.
    - Assumed: cut-offs, delivery days, no order endpoint, simulated history.
    - Next: Postgres, per-agent identity, Valio's order endpoint, Peppol.
- **Visual:** on the left, a ticket rail with five trap tickets; on the right, the Real / Assumed / Next strip.
  Footer: "Valio challenge mock · no real orders or payments".
- **Notes:** Zoha's research: show the number beside one success and one honest hold. The details are in
  `docs/ASSUMPTIONS.md` and `docs/NEXT-STEPS.md`.

### 6. Codex built it. Claude ran the room.
- **Evidence:**
  - **29 commits on main say "Built by Codex"**: the one-brain engine, the Gemini chat agent (#114), the kitchen
    interview, the calendar, the QR kitchens, the allergen-proof fix, the agent-cancel fix (#115), the CRACI evidence
    pipeline (#116), and voice on one brain (#117).
  - Parallel git worktrees, each looping against real Gemini until the tests passed.
  - Claude briefed, reviewed and test-gated every merge.
  - Codex also attacked: *"free-from milk cleared a peanut ban"* (CRITICAL) was caught and fixed with a test.
- **Visual:** a lane diagram: Claude's control room fans out to Codex worktree lanes → "real-Gemini test ✓" →
  review → test gate → merge onto main. In the corner, the struck-through CRITICAL card.
- **Notes:** `docs/CODEX.md` has every run (model, effort, ask, result, PR). Name what the judges just used that Codex
  built: the chat agent.

### 7. Agents knock. The door checks. The chef decides.
- **Evidence:** the repo URL; "Valio challenge mock · no real orders or payments".
- **Visual:** the line, large. **[OPTION]** a QR code to `valio-front-door.onrender.com/#try` ("your own test kitchen,
  24 h; try to trick it"), only if the team trusts the live app with strangers.
- **Notes:** Close on the line. Hand out the QR cards only if the option is on.

### 8. Which build signed your order? **[ONLY IF CRACI LIVE]**
- **Evidence:**
  - CI runs on CRACI;
  - the live app fetches its own build's CycloneDX SBOM and network trace from the CRACI API, and publishes their
    hash, the vulnerability counts and the network destinations at `/.well-known/front-door-build.json`, linked from
    its signing keys.
- **Visual:** a chain: CRACI build → SBOM + network trace → `sbom_sha256` → `/.well-known/front-door-build.json` →
  signing keys → the signed order. Beside it, a real screenshot of the endpoint showing `"status": "ok"`.
- **Notes:**
  - Why the app fetches the evidence itself: CRACI's API refuses calls from its own runners (403).
  - If the endpoint isn't `ok`, drop this slide; slide 5 already says "CI on CRACI".
