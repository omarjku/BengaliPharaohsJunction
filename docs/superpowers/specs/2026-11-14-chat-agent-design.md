# Text Chat Agent Design

## Intent

Replace the template-written text response with a Gemini `generateContent` function-calling loop. Gemini writes the chef-facing answer; existing deterministic ordering, menu, profile, kitchen, and approval code remains the source of truth.

## Boundaries

- The agent may search, propose/change/cancel, inspect kitchen data, and plan menus.
- There is no approval tool. The chef approves on screen.
- A card is returned only for a tool result that contains the corresponding structured run; prose alone can never create an order card.
- The loop is limited to six tool calls and 25 seconds, with `/api/agent/ask` as the fallback.
- Existing `/api/agent/ask` behavior is unchanged.

## Approach

The chat module reuses `agent._http`, Gemini key/model configuration, and `agent._api_schema`. It injects quoted profile, standing-order, current-order, kitchen-context, date, and bounded conversation data into the system instruction. Tool adapters call existing pipelines and normalize their results for Gemini while returning full `AgentRun`/`MenuRun` cards to the client. The frontend sends text to `/api/agent/chat` and adapts returned cards into the existing `RunResult`/`MenuResult` view model.

## Acceptance

Offline fake-Gemini tests cover dispatch, approval safety, card grounding, and fallback. The required backend suite, frontend build/lint, and real scripted conversations are run before handoff.
