# Speed investigation — release-1

Date: 2026-11-14  
Label: `release-1`  
Target backend: `http://127.0.0.1:8781`

## Benchmark result

The requested real-backend run could not reach the application. Uvicorn and a direct socket probe both failed to bind
`127.0.0.1:8781` with `EPERM` in this sandbox. `scripts/speed_bench.py --base http://127.0.0.1:8781 --label release-1`
therefore recorded 10/10 transport errors: 0 approvable sessions, median approvable time `n/a`, and transport wall time
0.000–0.014 s (median 0.000 s). The generated 5.00× fallback speed-up is not a backend measurement.

## Three largest latency costs

1. Valio quote I/O is two serial upstream requests per cache miss: availability, then price (`backend/app/valio.py:109-115`).
   This is one extra network round trip on every new product/date set. Safe fix: issue both requests with
   `asyncio.gather` using the same client, then merge their responses. This file was outside task scope, so it is report-only.

2. The `/api/agent/ask` preflight awaits the steering Decisions call before starting understanding
   (`backend/app/ask.py:1188`, then `:1253`). That makes one model RTT additive to every uncached turn. Safe fix: start
   steering and understanding together; retain the current guard precedence before executing any action. This file was
   outside task scope, so it is report-only.

3. `_pipeline` previously waited for the batched diet-risk Gemini read before starting each item's query expansion.
   Those independent reads are now started together in `backend/app/agent.py:1190-1194`; `candidates()` reuses the
   expansion module's existing cache, so matching behavior is unchanged. The existing measured match fan-out is
   0.5–0.9 s for 20 hits, while the superseded serial rank call was 5–8 s (`agent.py:821-829`).

## Additional safe change

The TTL caches did not coalesce identical calls that arrived concurrently. `agent.py:_gemini` and
`agent.py:_decisions` now share in-flight tasks for the exact same key, with shielded waiters and the existing
fallback behavior. A local fake-client check confirmed two concurrent calls produced one Gemini request and one
Decisions request; results remained equal.

## Verification

- Targeted backend tests: `88 passed` (`tests/test_agent.py`, `tests/test_quantity.py`, `scripts/tests/test_speed_bench.py`).
- Full backend suite: `634 passed, 21 failed, 1 skipped`; the failures are pre-existing menu crashes on missing
  `ReasonCode.COVERAGE_LOW` in files outside this task.
- Real speed benchmark: unverified because the sandbox forbids binding the requested port.
