---
name: Front Door
colors:
  surface: '#FFFFFF'
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
  secondary: '#565f69'
  on-secondary: '#ffffff'
  secondary-container: '#dae3ef'
  on-secondary-container: '#5c656f'
  tertiary: '#3d464d'
  on-tertiary: '#ffffff'
  tertiary-container: '#545d65'
  on-tertiary-container: '#cdd6e0'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#d5e3ff'
  primary-fixed-dim: '#a8c8ff'
  on-primary-fixed: '#001b3c'
  on-primary-fixed-variant: '#004689'
  secondary-fixed: '#dae3ef'
  secondary-fixed-dim: '#bec7d3'
  on-secondary-fixed: '#141c25'
  on-secondary-fixed-variant: '#3f4851'
  tertiary-fixed: '#dae3ed'
  tertiary-fixed-dim: '#bec7d1'
  on-tertiary-fixed: '#141d24'
  on-tertiary-fixed-variant: '#3f4850'
  background: '#F4F5F7'
  on-background: '#191c20'
  surface-variant: '#e1e2e8'
  border: '#D9DDE2'
  good: '#1E7A3C'
  good-bg: '#E8F5EC'
  warn: '#8A5A00'
  warn-bg: '#FFF4DC'
  bad: '#B3261E'
  bad-bg: '#FDECEA'
typography:
  headline-lg:
    fontFamily: Inter
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 34px
    letterSpacing: -0.01em
  headline-lg-mobile:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 30px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.005em
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
  label-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
  label-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.04em
  numeric-table:
    fontFamily: Inter
    fontSize: 14px
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
  gutter: 1rem
  gutter-desktop: 1.5rem
  margin: 1rem
  margin-desktop: 2rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2rem
---

## Brand & Style

This design system delivers an operational supervision console engineered specifically for head chefs overseeing autonomous purchasing agents. Built on principles of Nordic restraint and utilitarian precision, the visual environment prioritizes clarity, emotional equilibrium, and cognitive efficiency over conversational flourishes.

### Aesthetic Direction: Nordic Utilitarianism
- **Calm, High-Legibility Control:** Heavy use of tranquil neutral negative space (`#F4F5F7` canvas, `#FFFFFF` surfaces), structured by hairline borders (`#D9DDE2`).
- **Chromatic Discipline:** Absolute avoidance of decorative color. Color exists exclusively to convey operational status (`good`, `warn`, `bad`) and system focus (`accent`). 
- **Non-Conversational:** Completely eschews conversational paradigms. There are no avatars, chatbot bubbles, typing indicators, or anthropomorphized agent personalities.
- **Glanceability:** Formulated for high-pressure kitchen operations where decisions must be evaluated, audited, and confirmed in fractions of a second between prep tasks.

## Colors

The palette operates under a strict semantic protocol. The interface runs entirely in `light` mode; there is no dark mode. 

### Semantic Pairings
Status cues must never rely on color alone—they always pair a high-contrast foreground tone with its tinted background container alongside an explicit symbol or text:
- **Good / Ordered:** `#1E7A3C` on `#E8F5EC`. Applied to completed orders and AI confidence values $\ge 0.80$.
- **Warn / Needs Attention:** `#8A5A00` on `#FFF4DC`. Applied to items requiring verification, threshold breaches, and confidence values $< 0.80$.
- **Bad / Refused:** `#B3261E` on `#FDECEA`. Applied to rejected lines, cut-off violations, and allergen incompatibilities.

### Structural Neutrals & Accent
- **Primary Accent (`#0B5CAD`):** Reserved for primary interactive controls, anchor links, focus rings, and indicating selected operational rows.
- **Accent Soft (`#E7F0FA`):** Used for highlighting the active/chosen item row background.
- **Text Tones:** Primary typography renders in `#1C1F23`. Subordinate context, metrics, and metadata render in `#5D6670`.
- **Canvas & Surface:** Base application canvas is `#F4F5F7` with structural surfaces strictly `#FFFFFF`. Borders are hairline 1px `#D9DDE2`.

## Typography

Typography is clean, functional, and systematic. **Inter** is specified across all hierarchy tiers.

### Rules & Formatting
- **Tabular Figures:** All numeric displays (pricing, quantities, percentages, SKU weights) must activate `font-variant-numeric: tabular-nums` to ensure exact column alignment in tables and financial rollups.
- **Financial Units:** Always show explicit currency and units (e.g., `€1,560.00`, `1,000 × 1 L`). Numeric quantities and prices are aligned to the right.
- **Section Headers:** Small section anchors (`label-sm`) utilize uppercase styling with explicit letter tracking (`0.04em`).
- **Casing:** Sentence case is strictly applied everywhere else. Buttons and interactive elements must never be set in all-caps.

## Layout & Spacing

The layout is built on a 4px geometric base unit with structural limits optimized for desk console and handheld viewports.

### Breakpoints & Layout Container
- **Desktop:** The primary viewport. Max content area width is 1120px, centered within a 1280px standard desktop shell. Outer margins are `2rem` (32px), with card padding at `1.5rem` (24px).
- **Mobile (375px):** Outer canvas margins collapse to `1rem` (16px), and card padding reduces to `1rem` (16px).
- **Grid Structure:** Fluid 12-column grid on desktop screens; single-column stacked layout on mobile. Substitute comparison cards switch from a 3-column horizontal array on desktop to a sequential stack on mobile.
- **Inter-Card Spacing:** Standard spacing between modular operational cards is fixed at `1rem` (16px).

## Elevation & Depth

This system adheres to a pure flat elevation architecture. Surfaces convey spatial order through borders and edge accents rather than drop shadows.

- **Flat Planes:** Content cards, tables, and sidebars utilize a 1px solid border (`#D9DDE2`) against the `#F4F5F7` background with `box-shadow: none`.
- **Status Border Indicators:** Cards and selected rows utilize a 4px solid inset left edge corresponding to status (`#1E7A3C`, `#8A5A00`, `#B3261E`, or `#0B5CAD`).
- **Modal Layer:** The sole exception to the shadowless rule is the API keys / authentication modal overlay, which uses a low-intensity, highly diffused ambient elevation:
  `box-shadow: 0 8px 24px rgba(28, 31, 35, 0.12)`.

## Shapes

The geometric silhouette balances technical precision with subtle corner rounding.

- **Containers & Controls (8px):** All actionable cards, input fields, standard tables, and operational buttons use an 8px border radius (`roundedness: 2`).
- **Status Chips & Pills (999px):** Status indicators, confidence meters, and non-interactive fact tags use full pill geometry (`border-radius: 9999px`).

## Components

### Status Chip
- **Anatomy:** 999px pill containing an explicit status icon and concise label: `Ordered` (good), `Needs your OK` (warn), or `Refused` (bad).
- **Colors:** Derived from semantic pairings (e.g., `#1E7A3C` text on `#E8F5EC` background). Never display status with color alone.

### Decision Card (Hero Component)
- **Visual Anchors:** 8px radius, white surface, 1px `#D9DDE2` border, with a 4px left vertical border in the respective status color.
- **Hierarchy:** 
  1. Top: Semantic Status Chip.
  2. Headline: Single clear summary sentence (e.g., "Above your €1,500 auto-approve limit").
  3. Body: Ordered itemized list detailing explicit triggers with inline icons and recommended adjustments. Top reasons are always visible without accordion toggles.
  4. Actions: Action buttons arranged along the bottom edge. Exactly one primary action per card.

### Buttons
- **Height & Spacing:** Uniform 40px height, 16px horizontal padding, 8px radius, Inter 14px medium/semibold.
- **Primary:** Solid `#0B5CAD` background, `#FFFFFF` text. Focus state receives a 2px `#0B5CAD` ring with 2px white offset.
- **Secondary:** `#FFFFFF` background, 1px `#D9DDE2` border, `#1C1F23` text.
- **Destructive ("Reject"):** `#FFFFFF` background, 1px `#B3261E` border, `#B3261E` text.

### Confidence Pill
- **Display:** Small pill reading the agent model and confidence score (e.g., `Gemini 0.96`).
- **Threshold Rule:** Values $\ge 0.80$ render using the `good` pair (`#1E7A3C` / `#E8F5EC`); values $< 0.80$ render using the `warn` pair (`#8A5A00` / `#FFF4DC`). Paired with a concise explanation line.

### Product Rows & Selection Lists
- **Structure:** Left side displays Product Name, Brand, availability text ("In stock, order by Sun 17:00", "Cut-off passed", or "Stock unknown"), and fact tags. Right side displays quantity and line total in tabular numerals.
- **Chosen State:** Background changes to `#E7F0FA` (`accent-soft`), left edge highlighted with a 4px `#0B5CAD` border, and includes a "Chosen" tag.
- **Rejected State:** Content text muted (`#5D6670`) with inline explanation of exclusion.

### Fact Tags
- **Structure:** Static pill components with `#F4F5F7` background fill and `#5D6670` text (e.g., "on time 97%", "origin FI", "1.2 kg CO₂/kg"). Non-interactive.

### Input Fields
- **Metrics:** 40px height, 1px `#D9DDE2` border, 8px radius.
- **Requirements:** Input labels must always sit permanently above the field. Never use placeholder text as a substitute for labels. Active focus produces a 2px `#0B5CAD` outline.

### Substitute Comparison Cards
- **Desktop:** 3-up horizontal grid displaying options categorized as "Best", "Better", and "Good".
- **Content:** Each card lists price, reliability score, and a clear "Why it's safe" justification line.

### Audit Timeline
- **Format:** Linear vertical track with solid nodal markers. Each event highlights timestamp, acting agent ("Buyer agent", "Valio front door", "Chef Aino"), compact status badge, and descriptive rationale.