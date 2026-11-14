# Gemini in Front Door

This is the current Gemini integration behind the text, photo, and voice paths in
`origin/main`. The backend keeps the API key server-side; the browser receives
transcripts, cards, structured results, and decision reasons. Gemini interprets
language and adds uncertainty. Python and the front door remain authoritative for
catalogue facts, prices, stock, quantities, dates, mandates, approval, and audit.

## The main text brain: function-calling chat

`POST /api/agent/chat` is driven by `backend/app/chat_agent.py`. Gemini receives a
bounded set of kitchen tools:

- `search_products` for read-only catalogue, price, stock, claim, and allergen lookup;
- `propose_order`, `change_order`, and the pending-order `cancel_order` adapter;
- `current_order`, `kitchen_profile`, and `kitchen_context` for quoted kitchen facts;
- `check_assumptions` for independent uncertainty checks; and
- `plan_menu` for a proposal that never places an order by itself.

The agent loop is bounded to a 19-second turn and six tool calls. It sends Gemini's
function declarations, appends the complete returned model content unchanged (so
`thoughtSignature` parts survive the next request), executes the requested tools,
sends all function responses for that turn together, and repeats until Gemini returns
the answer. A provider or loop failure is surfaced or routed through the documented
deterministic `/api/agent/ask` fallback; it is not hidden as a successful order.

Every turn is guarded with the chef's original words in the `_TURN` context: the
steering/injection score and auto-approval stripping are computed from that raw turn,
then passed into the deterministic engine. A tool result must produce a card before
the chat claims an order exists. Gemini has no approval authority, and assumptions or
low-confidence matches become a question or a held proposal.

## Gemini models and call paths

The defaults are in `backend/app/config.py`:

| Model | Code path | Role |
|---|---|---|
| `gemini-4-hydrogen` | `chat_agent._generate_content` | Main text conversation: understands the chef, chooses tools, explains returned cards, and handles typed pending follow-ups. |
| `gemini-decision-1` | `chat_agent._check_assumptions` and `agent._decisions` | Calibrated typed `noul` questions for product fit, quantity, substitutions, dates, plausibility, steering, menu assumptions, and rules. |
| `gemini-4-hydrogen` | `agent.parse`, `menu.parse_menu`, `profile.from_about`, `kitchen.log_from_text`, `rules.RestLLM` | Structured parsing for the deterministic order/menu, profile, kitchen-history, and mandate surfaces. |
| `gemini-4-hydrogen` | `vision._read` | Reads a JPEG/PNG/WEBP/HEIC list, menu board, pantry, or whiteboard; instruction-like text is data and never authority. |
| `gemini-3.5-transcribe-live` | `POST /api/voice/transcribe` | Push-to-talk transcription only; this route places nothing. |
| `gemini-3.8-live` | `WebSocket /api/live` | Native Talk audio over the same chat tools and deterministic engine. |

All structured calls use JSON response schemas, untrusted-text delimiters, bounded
inputs, and validation before state changes. On the Decisions path, independent
assumptions are batched: `check_assumptions` sends up to 40 typed questions in one
`/v1beta/decisions` request. Competing catalogue candidates remain separately judged
so one candidate cannot distort another's calibration. The configured buyer threshold
keeps a guess only when its `p_yes` clears that buyer's threshold; otherwise the chef
is asked.

## Voice uses the same brain

`backend/app/live.py` derives its order-mode declarations from `chat_agent.TOOLS` and
dispatches through `chat_agent._dispatch_tool`. Live therefore shares catalogue
search, proposal, change, current-order, kitchen-context, assumption, and menu logic
with text instead of maintaining a second ordering brain. The Live set removes
`cancel_order`; spoken cancellation says to tap Cancel on the order card.

Live recomputes the steering/auto-approval guard when the chef transcript changes,
never guards a tool from an empty transcript, and resets it at `turnComplete`. Every
voice-originated order or change carries the voice hold and waits for the chef's
on-screen approval. There is no voice approval tool. A Talk session is limited to five
minutes and two concurrent sessions per buyer.

## What is measured

The labelled product evaluation in `backend/eval/gemini_eval.py` contains 33 cases and
uses real Valio catalogue products. The 0.70 demo threshold produced 0 wrong automatic
orders and handled 14/15 correct product lines alone. Keep in mind: the 33-case set was tuned on itself, so this is development evidence rather than held-out proof. Traps include coffee milk versus milk, coffee cream versus cream, baking sugar sachets, dietary mismatches, and salted versus unsalted butter.

The chat-agent edge evaluation is a Gemini-graded estimate from
[`docs/testing/edge-eval-chat-2026-11-15.md`](testing/edge-eval-chat-2026-11-15.md):
97/164 cases passed (59.1%), median 3.85 seconds per turn, and 0 unsafe auto-orders
in all 164 cases, including 10 injection attempts. The report is not a deterministic
benchmark; its failure groups and manual-correction counts are included in the source
report.

## Safety boundary

Gemini cannot relax a mandate, invent a product id, price, stock or delivery day,
override an allergen or cut-off, approve a cart, or change an approver-controlled
rule. Every result is validated before it reaches catalogue search, quantity
resolution, Valio quotes, the gate, order storage, or audit. A timeout, malformed
answer, budget exhaustion, or invalid probability is unverified and follows the
buyer's uncertainty policy.

Further evidence: [`GEMINI-evidence.md`](GEMINI-evidence.md), [`VOICE.md`](VOICE.md),
[`backend/eval/`](../backend/eval/), and the fixtures in [`demo-images/`](demo-images/).
