# Front Door: presentation (10 slides)

**Look:** the existing deck's system (`docs/deck/index.html`): a white or off-white field, graphite text, blue
`#0B5CAD`, amber for human review, green for confirmed, red only for danger. On top of that, one motif from draft B: the
**thermal kitchen ticket with a stamp** (ORDERED / HELD / NOT ORDERED). One proof point per slide, and at most 25 words
of body text. Real screenshots go in phone frames.

**Truth tags:**
- **[only after voice ships]** and **[only if PR #116 ships with live evidence]** mark text that stays off the slide
  until it's true.
- Numbers come from `wow-and-dont-show.md`, appendix.

---

### 1. Front Door
- **Line:** Agents knock. The door checks. The chef decides.
- **Visual:** the planted handwritten list, full bleed (`docs/demo-images/handwritten-list-planted.jpg`), with a
  white band at the bottom holding the title. The yellow sticky note stays readable. A thin blue vertical line, the
  door, cuts through the note's corner (from draft A).
- **Notes:** One breath: the team (Omar Kassem, Fathia Fairuz Zoha) and the line. "The handwriting is real; the
  scenario is a demo recreation of Valio's example request." No market statistics.

### 2. Would you let an AI spend your money?
- **Line:** Valio's example: "1,000 litres of lactose-free milk by Monday."
- **Visual:** on the left, Valio's sentence as a large pull quote, cited "Valio Aimo, challenge brief". On the right, the
  held approver card (`docs/design/screens/final/2-milk-1500-approval-390.png`) in a phone frame, with three amber
  annotations: *spend · allergen · cut-off* (from draft A).
- **Notes:** Valio Aimo serves 20,000+ professional kitchens. Buyers will bring their own agents; who checks them at
  Valio's side? This is not a chatbot replacing the webshop. It's the interface any agent must pass through.

### 3. Agents knock. The door checks. The chef decides.
- **Line:** The agent proposes. The door decides. Only a human approves.
- **Visual:** the last frame of the video's architecture animation:
  - inputs (text, photo, voice) → **Gemini agent** with deterministic tools (17,546 products, live quote, units,
    allergens, menus);
  - a ticket → the **blue door** with five checks → ORDERED / HELD / NOT ORDERED → an "Ed25519 signed" stub;
  - an *OpenAPI · MCP* port with ghost agents docking.
- **Notes:**
  - The mandate is stored server-side; an agent can't send its own.
  - Approval re-runs the gate with fresh quotes, so a changed price keeps the order pending.
  - Keep it under 15 seconds.

### 4. Follow one order
- **Line:** Read → matched → priced → held → approved → signed.
- **Visual:** a strip of six real phone screens joined by one sliding ticket:
  1. the photo read, with the note flagged;
  2. the Decisions score;
  3. the fresh quote;
  4. HELD;
  5. the approve tap;
  6. "Signed by the front door ✓".
- **Notes:** This is J1 (30%) in one picture: request → lookup → order or approval, against Valio's challenge mock, not
  isolated pieces. "You'll do this yourself in a minute."

### 5. €1,560 > €1,500
- **Line:** The right milk, and still one tap by the chef.
- **Visual:** a giant inequality (from draft A) as the whole composition. The approver phone overlaps its right edge.
  Two small stamps below: *hard rules refuse* · *sign-off rules hold*.
- **Notes:** This is J3.
  - The numbers are true for the typed, milk-only order `1000 L lactose-free milk for Monday`. Never put them on the
    photo cart, which costs more.
  - Hard rules: allergens, claims, maximum price, cut-off. Sign-off rules: the €1,500 limit, the per-line cap, the
    weekly budget, the 90% reliability floor.
  - An agent key gets 401 on approve, and since #115 it can't cancel a confirmed order.

### 6. Gemini measures doubt. The mandate controls permission.
- **Line:** 33 labelled cases · threshold 0.70 · 0 wrong automatic orders.
- **Visual:** the score-distribution chart (`docs/deck/assets/gemini-distribution.png`) with the dashed 0.70 line;
  call-outs for coffee milk at **0.115** and lactose-free milk at **0.897**. A single amber arrow below the line: "ask
  the chef". Three role chips: *Reads* (text, photo, Live) · *Scores* (Decisions) · *Talks* (Live native audio).
- **Notes:**
  - Coffee milk once scored 0.72 (from our notes), above the line. Our QA caught it, not the calibration, and the
    reworded question now scores it 0.115.
  - Gemini can only add caution.
  - On/off test, 5 requests: without Gemini, nothing was ordered alone. It loses autonomy, not safety.
  - This is separation on the tuned set, not a held-out guarantee.

### 7. Every trap becomes a question
- **Line:** Never a silent guess: always a reason and an alternative.
- **Visual:** a kitchen ticket rail with five tickets clipped on:
  - CUT-OFF PASSED, "AVAILABLE MONDAY" ANYWAY;
  - 999999 = UNKNOWN, NOT UNLIMITED;
  - NO ALLERGEN DATA → ASK;
  - SUBSTITUTES: SAME KIND, ALLERGEN-SAFE;
  - INSTRUCTION IN A PHOTO → IGNORED.
- **Notes:** J4. The traps come from the mock data: Terminal cut-offs about 4 days ahead, about 15% of products
  undeliverable. Decision D6: when the data is uncertain, bring it to the human with the reason and alternatives.

### 8. Not our agent's door
- **Line:** OpenAPI 3.1 · JSON Schema · MCP · Ed25519 signed statements · MIT.
- **Visual:** three plugs into one door: our Gemini agent, Claude over MCP, and "your agent" over OpenAPI. Then the
  Valio view with "Signed by the front door ✓". Below, a strip:
  - **Real:** fresh quotes from the Valio challenge mock, the full catalogue, Gemini, signing, MCP, CI on CRACI.
  - **Assumed:** cut-offs, delivery days, no order endpoint, simulated history.
  - **Next:** Postgres, per-agent identity, Valio's order endpoint, Peppol.
  - Footer: "Valio challenge mock · no real orders or payments".
  - **[only if PR #116 ships with live evidence]**, add one more link to the chain: CRACI build → SBOM + network trace
    → `/.well-known/front-door-build.json` → the signing keys.
- **Notes:**
  - RFC 9421 agent signing is optional per buyer today.
  - GS1 allergen codes; the Peppol mapping is in `docs/STANDARDS.md`. Every assumption is in `docs/ASSUMPTIONS.md`.

### 9. Codex built it. Claude ran the room.
- **Line:** Built → real-Gemini tested → reviewed → shipped. Then attacked.
- **Visual:** a lane diagram:
  - **Claude control room** (brief) fans out to **parallel Codex worktrees**, each a build card:
    - Gemini chat agent `chat_agent.py` (#114);
    - engine v2 waves;
    - agent-cancel fix (#115);
    - CRACI evidence script (#116, *built; ships tonight* until merged);
    - **[only after voice ships]** voice on one brain.
  - Each lane loops *real-Gemini test ✓* and returns to **Claude: review → test gate → merge**.
  - Right column, "Codex as adversary", three struck-through findings:
    - free-from milk cleared a peanut ban (CRITICAL, f1a1328);
    - the agent could cancel under a fake chef sign-off (cca43f2);
    - every structured Gemini call silently failed with HTTP 400.
  - Footer: **24 commits on main say "Built by Codex"** · 28 logged review runs · 112 findings · 79 fixed.
- **Notes:** This is the Codex criterion: build, iterate, ship, and say so clearly.
  - Name one thing the judges just used that Codex built: the chat agent.
  - Fixes came with regression tests.
  - `docs/CODEX.md` has the run-by-run log.
  - Say "CRACI script built, evidence publication ships tonight" until #116 is live.

### 10. Try to trick it
- **Line:** Scan for your own test kitchen, live for 24 hours.
- **Visual:** a giant QR code to `valio-front-door.onrender.com/#try`, the three things to try, and a yellow sticky-note
  graphic reading "your note here". The closing line sits in the corner.
- **Notes:** Hand out the cards. Use mobile data if the venue Wi-Fi is shared (5 test kitchens per IP per hour), and
  keep the pre-minted kitchens ready. Close: "Agents knock. The door checks. The chef decides."
