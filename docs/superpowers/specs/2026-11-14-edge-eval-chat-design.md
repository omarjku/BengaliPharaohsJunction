# Chat Edge Evaluation Design

## Intent

Measure the current Valio J1/J2 behavior through the shipped Gemini function-calling chat endpoint, while keeping the legacy `/api/agent/ask` evaluator available for comparison. The report must expose pass rates, per-turn latency, and the amount of chef correction required instead of presenting the old 47/144 number as current.

## Approach

The evaluator will use one transport adapter per endpoint and normalize both response contracts into the existing compact grading view. The chat adapter will follow `scripts/chat.py`: new turns send `text`; continuation turns send `conversation_id`, and only answer a pending question with the public `follow_up` object. Multi-turn cases will be graded after every turn. The first passing turn determines corrections; cases that never pass are reported as unresolved.

The regression corpus will retain existing cases and add explicit phone cases for the reported vegan, gluten-free, relative-date, assumption, numeric follow-up, Valio milk, alternatives, and Finnish requests. Reports will be endpoint-specific and will record the short commit hash, buyer, host, endpoint, Gemini-graded-estimate status, group rates, median seconds per turn, manual-correction mean/distribution, and the top ten failures with likely source hints.

## Constraints and non-goals

- Do not change backend behavior or catalogue access.
- Do not sweep the catalogue; run the existing sequential evaluator against one smoke kitchen.
- Never persist or print API keys.
- Preserve the legacy `/ask` request/response behavior and existing evaluator tests.
- Do not commit or push this worktree.
