# Website Updates Changelog — 2026-03-23

**Author:** AeroCore Agent (port 9210)
**Date:** March 23, 2026
**Status:** Complete — deployed to production (areocore.com)

---

## 1. Materials Page (`/materials`)

### Section Reorder
- High-Performance Alloys → first
- Carbide Tooling → second
- Tungsten Materials → third (new dedicated section added)
- Tool Steel & HSS → fourth
- Production Surplus → fifth
- Aerospace Components → bottom

### Subtitle Update
- Reworded to: "From aerospace alloys and individual end mills to full plant liquidations..."
- End mills moved to 2nd position (not leading)

### New Tungsten Section
- Added dedicated Tungsten Materials section with 3 cards:
  - Tungsten Carbide Solids
  - Tungsten Powder & Granules
  - Pure Tungsten & Heavy Alloy

### Icons Replaced (all cards)
Every subcategory card icon replaced with material-specific SVGs:
- Inconel: flame (high-temp superalloy)
- Titanium: diamond gem (premium aerospace)
- Hastelloy: flask (chemical processing)
- Monel/Rene: hexagonal molecule (alloy structure)
- Carbide Inserts: diamond/rhombus insert shape
- End Mills: cylinder with flute lines
- Drills: pointed bit with shaft
- Boring Bars: horizontal bar with cutting tip
- Tungsten Solids: 3D cube
- Tungsten Powder: scattered particles
- Pure Tungsten: stacked rods
- M2/M42 HSS: circular saw blade
- Cobalt HSS: nested hexagons
- D2/A2: stamp/die press
- Unused Tooling: open box
- Plant Liquidations: truck
- Warehouse: building
- Turbine Blades: turbine fan
- Fasteners: hex bolt
- Engine Parts: jet engine (concentric rings)

---

## 2. Pricing Page (`/pricing`)

### Section Removed
- Deleted "Materials We Price" table — every row just said "Get Quote" (redundant)

### Section Renamed
- "Factors That Affect Your Price" → "What Drives Your Material's Value"
- Badge: "Pricing Factors" → "Maximize Your Return"
- Subtitle reworded to positive framing

### Icons Replaced (5 cards in value drivers section)
- Grade & Composition: stacked layers → ascending bar chart
- Material Condition: shield → sparkles (clean/quality)
- Quantity: truck → stacked weight blocks
- Market Conditions: kept chart line (already appropriate)
- Cobalt Content: clock → atom with orbital rings

---

## 3. How It Works Page (`/process`)

### Heading Reorder
- "Sell Your Carbide & Alloys" → "Sell Your Alloys & Carbide Tooling" (alloys first)

### Icons Replaced (3 cards)
- Online Quote Form: grid → clipboard with lines
- Transparent Pricing: shield → eye (transparency)
- Evaluation Criteria: heartbeat → magnifying glass

---

## 4. Site-Wide: "Carbide" → "Carbide Tooling"

Changed standalone "carbide" to "carbide tooling" across ALL pages where it's used as a product category:
- Page titles, meta descriptions, OG/Twitter tags, structured data
- Footer brand text on every page
- Visible headings and body copy

**Not changed** (intentionally):
- "tungsten carbide" (compound material name)
- Specific products: "carbide inserts", "carbide end mills", "carbide drills"
- SEO keywords meta tags
- FAQ questions/answers about the raw material
- Form dropdown options
- Customer testimonial quotes

### Pages affected:
- `/` (index)
- `/materials`
- `/pricing`
- `/process`
- `/about`
- `/faq`
- `/contact`
- `/contact/thank-you`

---

## 5. Site-Wide: Icon Overhaul

Replaced ALL generic/placeholder icons (suns, shields, stars, stacked layers) with context-specific SVGs across every page:

### About Page (7 icons)
- CNC & Machine Shops: sun → wrench
- Oil & Gas: clock → flame/droplet
- Defense: plain shield → shield with checkmark
- Tool & Die: grid → stamping press
- Aerospace Expertise: stacked layers → laboratory flask
- Any Quantity: grid squares → balance scale
- Transparent Process: shield → eye

### Home Page (7 icons)
- Aerospace Components: sun/compass → rocket
- High-Performance Alloys: clock spokes → stacked ingot bars
- Carbide Tooling: rotated diamond → end mill
- Tungsten Materials: flag/wave → 3D cube
- Tool Steel & HSS: down arrow → wrench
- Manufacturing Overstock: abstract bars → stacked boxes
- No Hidden Deductions: circle checkmark → document with checkmark

---

## Impact on Ads

**URL structure:** No changes — all existing URLs remain the same:
- `https://areocore.com/` (general)
- `https://areocore.com/materials` (material-specific ads)
- `https://areocore.com/contact` (direct CTA)
- `https://areocore.com/pricing` (pricing info)

**Tracking:** Google Ads gtag.js and conversion tracking unchanged.

**Landing pages:** Content improved and icons updated, but page structure and CTAs are the same. No impact on conversion tracking or ad destinations.

---

## 6. Responsive Layout Fix (`/` homepage)

### Issue Found & Fixed
- Homepage had two `<div class="features-grid" style="grid-template-columns: repeat(3, 1fr)">` with inline styles that overrode CSS media queries
- This kept the "Competitive Pricing" and "Testimonials" sections stuck at 3 columns on all screen sizes (tablet/phone)
- **Fix:** Removed the inline `style` override — the `.features-grid` CSS class already defines 3 columns at desktop and properly collapses to 2-col (1024px) and 1-col (768px)

### Responsive Audit Confirmed
Full audit of all 9 pages confirmed responsive layout coverage:
- **3 breakpoints:** 1024px (tablet landscape), 768px (tablet/mobile), 480px (small phone)
- **Viewport meta tag:** present on all pages
- **Mobile navigation:** hamburger menu with animated dropdown at 768px
- **All grids collapse:** materials-grid, features-grid, process-grid, contact-grid, footer-grid
- **Typography scales:** `clamp()` on headings + media query overrides
- **Images:** global `max-width: 100%; height: auto`
- **Overflow protection:** `overflow-x: hidden` on body

---

## Deployment Log

| Time | Target | Commit Message |
|---|---|---|
| 2026-03-23 ~22:20 UTC | Production (areocore.com) | Website updates: icon overhaul, carbide tooling site-wide, pricing page cleanup, materials page reorder |
| 2026-03-23 ~22:25 UTC | Production (areocore.com) | Fix: remove inline grid override breaking responsive layout on homepage |
| 2026-03-23 ~22:45 UTC | Production (areocore.com) | Final deploy: responsive fix + all accumulated changes |
