# Stitch v2: design reference only

Static HTML exported from Google Stitch (Tailwind via CDN), plus `DESIGN.md` (the design spec) and a `screen.png` per screen. Each `code.html` also has a small responsive block for phones and tablets.

**All content in these pages is mock.** It is layout and styling reference, not product behaviour:

- Names, numbers and claims are invented: Ravintola Kiela, Chef Jari M., the S-ryhmä / Restel Horeca contract, ISO 22000, 99.98% SLA, EUR 500 limit, engine version, latency, "verified deployments", "14 rules".
- Nothing here talks to the backend. The real app is in `frontend/`; every number it shows comes from the API (the real order limit is EUR 1,500).

Screens: `valio_front_door_overview` (also `valio_front_door_kitchen_os`, identical), `valio_front_door_order_terminal_decision_states`, `valio_front_door_menu_to_cart`.
