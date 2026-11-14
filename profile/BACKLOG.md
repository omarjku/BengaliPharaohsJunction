# T13 backlog (not in this version)

- **Gemini** (optional): onboarding question wording or profile summaries via the shared T09 wrapper in replay mode. Not needed for the core.
- **Seed loader / Lapland persona:** T14 seeds a restaurant persona by calling `add_memory` / `record_onboarding`; no loader here.
- **Past-order analytics** (usual quantities, weekly drift): only the read-only `PastOrders` reference exists.
- **Adapter** from the front door's audit log to `PastOrders`, and the front door calling `close_order` when an order closes (T07/M2).
- **NICE edge cases:** very long history paging, memory expiry by age, bulk import/export, per-kind retention.
- **Contract export:** JSON Schemas for `Memory` / `ProfileContext` (J5) if Omar's UI needs them.
