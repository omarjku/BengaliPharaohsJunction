# Codex log: Room 1 (docs and openness, J5)

Codex CLI 0.169.0, run from the repo root on branch `room1-docs`, Sun 15 Nov 2026 (Helsinki). Claude Code
(Opus 5.5) wrote the prompts, then fact-checked every Codex claim against the code before keeping it.

| # | Model, effort, sandbox | Ask | Result | Kept / rejected |
|---|---|---|---|---|
| 1 | `gpt-reserve`, max, workspace-write | Draft `README.md` for a judge with 3 minutes: pitch line, live links, mermaid diagram, run locally, API table, J1–J5 sections, team and tools | Full draft, ~140 lines | Kept most of it. Fixed: the mermaid labels had `(...)` inside `[...]`, which Mermaid rejects (now quoted, with the human approver added); `/api/agent/run` header set to `X-Agent-Key` (Room 3 is adding it); added the D6 rule and links to the three new docs |
| 2 | `gpt-reserve`, max, workspace-write | Draft `docs/ASSUMPTIONS.md`: every assumption and data trap, what we do about it (D6), the file that handles it | 13 traps, each with data, assumption and code path | Kept, after checking each code path against `valio.py`, `gate.py`, `quantity.py`, `orders.py`, `auth.py`. Rejected "the agent asks for a rephrased product" (not in the code); rewrote #11 for the agent key |
| 3 | `gpt-reserve`, max, workspace-write | Draft `docs/STANDARDS.md`: OpenAPI 3.1, JSON Schema, GS1 allergens and identifiers, Peppol BIS Order / UBL 2.1 mapping (mapping only) | Full mapping incl. Order Response codes and the UN/ECE Rec 20 unit gap | Kept. Checked: no GTIN in the slim catalogue or contracts (true); added that Valio's raw file has `gtin` / `salesUnitGtin` but `catalogue.py` drops them |
| 4 | `gpt-reserve`, max, workspace-write | Draft `docs/NEXT-STEPS.md`: prioritised path to production from the `ponytail:` comments | 12 priorities with why and rough work | Kept. Changed the `/api/agent/run` auth wording to match the agent key |
| 5 | `gpt-5.6-terra`, ultra, read-only | Fact-check README and the three docs against the code; list anything false | Still running at push time (Codex never blocks) | Pending: anything critical it finds gets a follow-up commit |
| 6 | `gpt-reserve`, max, workspace-write | Draft the M2 `agent.py` change (line facts, Finnish tie-break, why) | Stopped before it wrote anything: Room 3's price ranking landed on integration meanwhile, so the draft would have been based on an outdated `run()` | Rejected; Claude wrote the change on the current base (commit "M2 agent: ...") |
