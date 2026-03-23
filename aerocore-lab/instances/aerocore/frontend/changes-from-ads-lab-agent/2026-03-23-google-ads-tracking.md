# 2026-03-23 — Google Ads Tracking Installation

**Agent:** AeroCore Ads Lab (port 9211)
**Google Ads Account:** 580-872-1896 (Areocore)
**Tag ID:** AW-18034797214

---

## What Was Added

### 1. Google Tag (gtag.js) — All Pages

Added the Google Ads global site tag to the `<head>` of all 7 HTML pages. This loads Google's tracking library and registers the AeroCore Ads account.

**Files modified:**
- `public/index.html`
- `public/materials/index.html`
- `public/pricing/index.html`
- `public/process/index.html`
- `public/about/index.html`
- `public/faq/index.html`
- `public/contact/index.html`

**Code added (after `<head>`, before `<meta charset>`):**
```html
<!-- Google tag (gtag.js) — Installed by AeroCore Ads Lab Agent 2026-03-23 -->
<script async src="https://www.googletagmanager.com/gtag/js?id=AW-18034797214"></script>
<script>
window.dataLayer = window.dataLayer || [];
function gtag(){dataLayer.push(arguments);}
gtag('js', new Date());
gtag('config', 'AW-18034797214');
</script>
```

### 2. Conversion Tracking — main.js

Added conversion event firing for three actions in `public/js/main.js`.

**File modified:** `public/js/main.js`

**Changes:**
- Added `trackConversion()` helper function at the top of the IIFE
- Quote form submission fires conversion on submit
- Phone call links (`tel:`) fire conversion on click
- Email links (`mailto:`) fire conversion on click

**Conversion Actions:**

| Action | send_to Label | Value | Trigger |
|--------|--------------|-------|---------|
| Quote Form Submission | `AW-18034797214/RXzGCMrnjo4cEJ7V1JdD` | $50 | Form submit |
| Phone Call Click | `AW-18034797214/iX9QCM3njo4cEJ7V1JdD` | $25 | Click on `tel:` link |
| Email Click | `AW-18034797214/zORLCNDnjo4cEJ7V1JdD` | $10 | Click on `mailto:` link |

### 3. Pre-existing Conversion (not modified)

The Google Ads account already had a "Contact" conversion action (ID: 7544904953, label: `29heCPm52I0cEJ7V1JdD`). This was not installed on the website — it may have been auto-created during account setup.

---

## How to Revert

To remove all Google Ads tracking:

1. **HTML pages:** Delete the gtag.js `<script>` block (8 lines starting with `<!-- Google tag`) from each of the 7 HTML files
2. **main.js:** Remove the `trackConversion()` function and the three tracking blocks (phone, email, form conversion line)
3. The conversion actions in Google Ads can be paused/deleted from the Ads dashboard

---

## Deployment Note

These changes are in the local development files. They need to be **deployed to Cloudflare Pages** to take effect on the production site (areocore.com). The frontend lab agent (port 9210) handles deployments.
