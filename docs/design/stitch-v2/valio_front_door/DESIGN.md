---
name: Valio Front Door
colors:
  surface: '#f8f9ff'
  surface-dim: '#d8dadf'
  surface-bright: '#f8f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f3f9'
  surface-container: '#eceef3'
  surface-container-high: '#e6e8ed'
  surface-container-highest: '#e1e2e8'
  on-surface: '#191c20'
  on-surface-variant: '#424751'
  inverse-surface: '#2e3135'
  inverse-on-surface: '#eff0f6'
  outline: '#727783'
  outline-variant: '#c2c6d3'
  surface-tint: '#115eaf'
  primary: '#004485'
  on-primary: '#ffffff'
  primary-container: '#0b5cad'
  on-primary-container: '#c0d6ff'
  inverse-primary: '#a8c8ff'
  secondary: '#575f6b'
  on-secondary: '#ffffff'
  secondary-container: '#d8e0ee'
  on-secondary-container: '#5b636f'
  tertiary: '#723200'
  on-tertiary: '#ffffff'
  tertiary-container: '#974400'
  on-tertiary-container: '#ffcaad'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#d5e3ff'
  primary-fixed-dim: '#a8c8ff'
  on-primary-fixed: '#001b3c'
  on-primary-fixed-variant: '#004689'
  secondary-fixed: '#dbe3f1'
  secondary-fixed-dim: '#bfc7d5'
  on-secondary-fixed: '#141c26'
  on-secondary-fixed-variant: '#3f4753'
  tertiary-fixed: '#ffdbc9'
  tertiary-fixed-dim: '#ffb68d'
  on-tertiary-fixed: '#321200'
  on-tertiary-fixed-variant: '#763300'
  background: '#f8f9ff'
  on-background: '#191c20'
  surface-variant: '#e1e2e8'
typography:
  headline-xl:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-xl-mobile:
    fontFamily: Inter
    fontSize: 26px
    fontWeight: '700'
    lineHeight: 34px
    letterSpacing: -0.01em
  headline-lg:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.005em
  headline-sm:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 24px
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  label-lg:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
  label-md:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.02em
  label-sm:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '700'
    lineHeight: 14px
    letterSpacing: 0.04em
  numeral-lg:
    fontFamily: Inter
    fontSize: 28px
    fontWeight: '700'
    lineHeight: 32px
    letterSpacing: -0.02em
  numeral-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 20px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 1.5rem
  gutter-mobile: 0.75rem
  margin: 2rem
  margin-mobile: 1rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2.5rem
---

## Brand & Style

This design system serves high-velocity Finnish institutional and professional kitchens: municipal catering leads, head chefs, dietary coordinators, and inventory clerks operating under strict delivery windows, flour dust, steam, and high-glare stainless steel environments.

The visual style is rooted in **Nordic Utilitarian Functionalism**. It avoids tech-startup novelty, gratuitous glassmorphism, decorative glows, and speculative AI flourishes. Every element prioritizes legibility, spatial honesty, tactile clarity, and uncompromising operational reliability. The interface functions like a precision culinary tool: durable, unpretentious, quiet, and instantly comprehensible during peak prep shifts.

### Guiding Principles
- **Clarity Over Embellishment:** High contrast, deliberate density, and predictable layouts supersede visual whimsy. No emojis, no decorative gradient sweeps, and no non-standard gesture patterns.
- **Physical Resilience:** Interfaces accommodate damp hands, greasy touch screens, low-angle wall-mounted terminals, and sunlight reflection through dock doors. Target hit areas never drop below 44px.
- **Institutional Integrity:** Colors convey explicit structural status—inventory arrival, batch certification, allergen warnings, or financial line reconciliation—never decorative flair.

## Colors

The palette is engineered exclusively for light environments, anchored by a warm architectural off-white canvas that minimizes eye fatigue during long shifts under 5000K commercial fluorescent illumination.

### Core Swatches
- **Canvas Base (`#fbfaf7`):** Warm oat neutral. Avoid pure optical white for page backdrops to eliminate glare.
- **Surface Elevation (`#ffffff`):** Pure white used exclusively on cards, modals, and input fields to elevate content cleanly off the canvas.
- **Structural Borders (`#e2ded7` / `#e5e2db`):** 1px tactile delineation between containers and tables. Never rely on borderless drop shadow separation alone.
- **Ink Primary (`#1c1f23`):** High-density carbon black for primary text, numeric metrics, and table heads, guaranteeing WCAG AAA compliance.
- **Muted Slate (`#59616d`):** Supporting metadata, unit indicators, subheaders, and helper copy.
- **Primary Brand Accent:** Valio Royal Blue (`#0b5cad`), with interactive state steps at Hover (`#084a8c`) and Pressed/Active (`#06396b`).

### Semantic Status Tokens
Status indicators use saturated, unambiguous functional tones with matched pale background tints and 1px bounding borders. Never use left-accent border stripes; apply explicit full-pill containment:
- **Success / Received:** Deep Forest Green (`#1e7a3c`) on pale mint tint (`#eef7f0`), border `#cde7d3`.
- **Review / Pending:** Deep Warm Amber (`#8a5a00`) on raw butter tint (`#fff6e3`), border `#f3dfb6`.
- **Blocked / Allergen Alert / Error:** Nordic Crimson (`#b3261e`) on pale blush tint (`#fdf2f2`), border `#f8d0cf`.

## Typography

The typographic hierarchy utilizes a clean Scandinavian neo-grotesque structural stack (`Inter`, falling back gracefully to system native sans: `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif`). It prioritizes rapid scan speed and eliminates ambiguity between glyphs (such as `1`, `I`, and `l`).

### Formatting & Treatment Rules
- **Tabular Numerals Mandatory:** All numeric displays (prices in EUR, kilogram units, pallet counts, GTIN codes, lot numbers, temperature readings) must enforce `font-feature-settings: "tnum" 1, "cv05" 1`. Columns of data must align vertically on the decimal point.
- **Zero Italicization:** Slanted typography reduces legibility through steam, water droplets, and angled viewing. Italics are prohibited across all UI components.
- **Labels & Microcopy:** High-contrast, slightly tracked uppercase or semi-bold labels (`label-sm`, `label-md`) are deployed for batch statuses, cold-chain confirmations, and tax breakdowns.

## Layout & Spacing

The layout model implements a structured, high-density fluid grid that stabilizes procurement workflows across 10-inch rugged kitchen tablets, dockside terminals, and desktop purchasing screens.

### Grid & Canvas Hierarchy
- **Desktop (>= 1200px):** 12-column fluid grid, 2rem margins, 1.5rem gutters. Max-width container capped at 1440px to preserve comfortable scan distances for multi-line order manifests.
- **Tablet (768px - 1199px):** 8-column fluid grid, 1.5rem margins, 1rem gutters. Optimized for mounted horizontal tablet mounts beside prep lines.
- **Mobile (< 768px):** 4-column fluid grid, 1rem margins, 0.75rem gutters. Primary actions sit sticky within thumb reach at the base.

### Layout Principles
- **No Floating Content:** All interactive data resides within bounded surfaces. Content never floats unanchored over the canvas background.
- **Predictable Dense Cadence:** Form fields, stock tables, and quantity pickers maintain strict 4px / 8px incremental spacing steps (`space-xs` to `space-xl`) to preserve uniform alignment when nesting complex requisition data.

## Elevation & Depth

Visual hierarchy is maintained via physical surface layering and crisp structural outlines rather than heavy atmospheric shadows. Glassmorphism, blurred scrims, multi-color drop shadows, and neon lighting effects are strictly forbidden.

### Elevation Levels
- **Canvas Base (Level 0):** Hex `#fbfaf7`. Flat, resting plane for all master screen layouts.
- **Surface Cards & Paneling (Level 1):** Hex `#ffffff` background with an uninterrupted `1px solid #e2ded7` border. Paired with a delicate, sharp architectural shadow: `0 1px 3px rgba(28, 31, 35, 0.05)`.
- **Dropdowns, Floating Drawers & Popovers (Level 2):** Pure white `#ffffff`, bordered by `1px solid #d5cfc5`, elevated via an authoritative structural shadow: `0 4px 12px rgba(28, 31, 35, 0.08)`.
- **Modals & Emergency Confirmations (Level 3):** Centered `#ffffff` container over an opaque dark wash (`rgba(28, 31, 35, 0.60)`). Backdrop filters are limited to standard `none` to maintain absolute GPU performance on budget institutional tablets.

### Rule of Lines
Whenever two surfaces meet at the same elevation level, division is achieved via a crisp `1px solid #e5e2db` rule. Never rely on white-on-light-gray contrast alone to indicate boundary edges.

## Shapes

The design system enforces a disciplined geometric corner radius of **12px (`0.75rem` / roundedness 2)** on cards, modal surfaces, and primary containers, balancing Nordic warmth with technical precision.

### Geometric Rules
- **Interactive Controls (Buttons, Text Inputs, Selects):** Uniform `8px` corner radius to provide tactile focus without turning into informal organic blobs.
- **Status Badges & Pill Chips:** Full pill radius (`9999px`) for metadata markers, category chips, and order state indicators. This immediately separates them conceptually from actionable rectangular input fields.
- **Cards & Drawer Enclosures:** Strict `12px` corner rounding. Nested containers within cards must step down to `6px` or `8px` to maintain concentric visual harmony.

## Components

### Buttons & Touch Targets
- **Physical Sizing:** Minimum touch boundary of `44px` height across all viewports (default height: `48px` for primary procurement interactions).
- **Primary Button:** Solid Valio Royal Blue (`#0b5cad`) background, `#ffffff` text, weight `600`, `8px` radius. Hover: `#084a8c`, Active: `#06396b`. Focus-visible: 2px offset solid `#0b5cad` ring.
- **Secondary / Utility Button:** Crisp `#ffffff` background, `1px solid #e2ded7`, `#1c1f23` text. Hover: `#fbfaf7` with `#1c1f23` border.
- **Destructive Button:** High-contrast Crimson `#b3261e` border or fill, reserved strictly for irreversible operations (canceling immediate logistics dispatch).

### Input Fields & Steppers
- **Height & Frame:** `48px` height, `1px solid #e2ded7`, white background, `8px` radius.
- **Active State:** Sharp `2px solid #0b5cad` outline with zero exterior blur haze.
- **Quantity Steppers:** Dedicated split `[-]` and `[+]` physical tap zones (min `44x44px`), flanking a centered bold tabular integer. Designed for rapid pallet and case incrementation.

### Status Badges & Honest Outcome Chips
- **Design Structure:** Full pill border radius (`9999px`), internal horizontal padding `10px`, vertical padding `4px`.
- **Composition:** 6px solid circular indicator dot on the left, followed by concise uppercase/semi-bold status copy.
- **No Ambiguity:** Approved stock is green (`#1e7a3c`), temperature review is amber (`#8a5a00`), unfulfilled or blocked allergen lines are crimson (`#b3261e`).

### Data Tables & Manifest Lists
- **Structure:** Rows alternate or separate cleanly with `1px solid #e5e2db`. Row height is generous (`52px` minimum) to allow accurate thumb targeting on line-item edits.
- **Header:** Sticky top, `#fbfaf7` background, uppercase `11px` tracked labels (`#59616d`), bottom `2px solid #e2ded7` baseline.

### Collapsible 'Why' Audit Drawers
- **Function:** Institutional Finnish kitchen procurement requires clear auditing (e.g., automated milk substitution reasoning, cold-chain verification, tax category adjustments).
- **Styling:** Drawer panels slide from the right or expand accordion-style directly under the row with a `#ffffff` surface, bounded by `1px solid #e2ded7`. Includes an explicit close trigger, structured event timeline, and officer timestamp in tabular numbers.