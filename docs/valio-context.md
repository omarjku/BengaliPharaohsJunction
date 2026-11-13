# Valio Aimo: business context (from valioaimo.fi, pikatukku, valotilaus.fi; read Fri 13 Nov)

Use for the pitch, for personas, and for honest assumptions (J5). Facts below are from their public pages; **our interpretations are marked "→".**

## How customers buy today
| Channel | What it is | → What it means for our agent |
|---|---|---|
| **Delivery wholesale** (toimitustukku) | 25,000 products, delivered nationwide, ~24 h average, one invoice | This is what the mock API mirrors (availability, cut-offs, price) |
| **Cash & Carry** (Helsinki, Vantaa) | Walk-in stores, card or invoice; per-store stock shown online ("Helsinki: 5 pcs, Vantaa: 3 pcs") | Store-level stock exists in reality but **not in the mock API**: an assumption if we use it |
| **Click & Collect / "Order & Pick up"** | **Helsinki store only.** "Currently, pickup is not available elsewhere in Finland." | → The voice "for pickup" idea must offer pickup **only in Helsinki**, and say so |
| **VALO Tilauspalvelu** (since 2014) | Order directly from manufacturers (Atria, HKFoods, Saarioinen, Snellman, Valio, Froneri), delivered by Valio's network; **invoice and complaints go to the supplier**; recurring or one-time orders, with or without contract | → Very likely the API's **"Terminal"** products (quantity unknown). For a trust protocol: *who stands behind each claim*, Valio or the supplier? |
| **My Aimo** | Self-service: purchases, price lists, **margins**, purchase reports, digital wholesale card, recipe ideas, margin calculator | → The natural home for the buyer's profile/memory and the audit trail |

Customer types: **wholesale** (credit = invoice, or pay-now) and **direct** (VALO, invoice from the supplier).
Units on VALO look like `10.0 KG/AST`, `12 PCS/CRT`, `6 PCS/CS` → quantities really are packaging-dependent ("1,000 L isn't 1,000 of anything").
Cash & Carry top categories: industrial groceries 4,374 · nonfood 4,046 · frozen 2,964 · fresh products 2,445 · drinks 1,232 · fresh meat & fish 656 · fruit & veg 569.
Seasonal ranges (Christmas, glögi, campaign products) → the "proactive selling agent" scenario.

## What customers say they value
- **Survey** (Taloustutkimus, autumn 2025, n=141): **88%** find ordering easy, **84%** rate delivery reliability good, **NPS 73**.
  → Ordering is already easy *for humans*; our job is making it easy **and trustworthy for agents**, not replacing a UI people like.
- Three customer quotes, three different priorities:
  - **Rouhe restaurants, Äkäslompolo (Lapland):** "delivery reliability in Lapland is absolutely vital"
  - **Juvenes** (food services): Finnish dairy farmers, animal welfare, domestic production
  - **Uudenmaan leipä** (bakery): price; "after comparing prices, we have always ended up choosing Valio Aimo"
  → These are exactly the **per-buyer preferences** our onboarding should learn: reliability vs Finnish origin vs price. The same request can then get a different correct answer per customer (J2).
- Identity: all operating profits go back to Finnish dairy farmers.

## Pitch line
"The buyer's agent is the visitor, and Valio wants a front door." Agents welcome, on Valio's terms.
