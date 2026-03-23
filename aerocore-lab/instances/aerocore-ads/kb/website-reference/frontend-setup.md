# AeroCore Frontend Website — Reference for Ads Management

**Last Updated:** 2026-03-23
**Managed By:** AeroCore Lab instance (port 9210 backend / 9280 frontend)
**This Document:** Reference for the Ads instance — do NOT modify the frontend from this lab. All frontend work happens in the AeroCore instance at `http://localhost:9210/`

---

## URLs & Deployment

| Environment | URL | Platform |
|-------------|-----|----------|
| Production | https://areocore.com | Cloudflare Pages |
| Production (CF default) | https://aerocore.pages.dev | Cloudflare Pages |
| Production (Netlify backup) | https://aerocore-recovery.netlify.app | Netlify |
| Development | http://localhost:9280 | Node.js dev server |

**Domain:** areocore.com (registered on GoDaddy, DNS pointed to Cloudflare Pages)
**Cloudflare Account:** Industrialrefiners@gmail.com
**Cloudflare Account ID:** 3035758242236180b2d5931b7165b46d
**Cloudflare Project Name:** aerocore

## File Locations

| What | Path |
|------|------|
| Frontend root | `/Volumes/T9 Drive 1/SERVER7-AEROCORE/aerocore-lab/instances/aerocore/frontend/` |
| Public files | `/Volumes/T9 Drive 1/SERVER7-AEROCORE/aerocore-lab/instances/aerocore/frontend/public/` |
| Dev server | `/Volumes/T9 Drive 1/SERVER7-AEROCORE/aerocore-lab/instances/aerocore/frontend/server.js` |
| Theme config | `/Volumes/T9 Drive 1/SERVER7-AEROCORE/aerocore-lab/instances/aerocore/frontend/theme/theme.json` |
| Instance config | `/Volumes/T9 Drive 1/SERVER7-AEROCORE/aerocore-lab/instances/aerocore/lab.json` |

## Tech Stack

- **No frameworks** — pure vanilla HTML, CSS, JavaScript
- **Server:** Node.js HTTP server with static file serving
- **CSS:** Mobile-first, custom properties, no CSS framework (945 lines)
- **JS:** Vanilla ES6+ (`/js/main.js`, 3,645 bytes)
- **Fonts:** Google Fonts Inter (400-800)
- **Routing:** Clean URLs with server-side fallback routing

## Site Pages

| Page | URL Path | Purpose | Ad Landing Page? |
|------|----------|---------|-----------------|
| Home | `/` | Hero, materials overview, CTA | Yes — general campaigns |
| Materials | `/materials` | Detailed material categories with cards | Yes — material-specific ads |
| Pricing | `/pricing` | Pricing factors, market-driven pricing | Maybe — price-focused queries |
| How It Works | `/process` | 3-step process visualization | No |
| About | `/about` | Company background | No |
| FAQ | `/faq` | Schema.org FAQPage with structured Q&A | No |
| Contact/Quote | `/contact` | Quote request form | Yes — CTA destination |

## Landing Page URLs for Ads

Use these in ad campaigns:

```
Homepage:        https://areocore.com/
Materials page:  https://areocore.com/materials
Pricing page:    https://areocore.com/pricing
Quote form:      https://areocore.com/contact
```

**With UTM parameters:**
```
https://areocore.com/contact?utm_source=google&utm_medium=cpc&utm_campaign={campaign_name}&utm_content={ad_variation}&utm_term={keyword}
```

## Contact Information (on website)

| Field | Value |
|-------|-------|
| Phone | (949) 239-8912 |
| Email | Info@AreoCore.com |
| Hours | Mon-Fri 8am-5pm PT |
| Location | California, USA |
| Owner | Chino Cooper |

## SEO Status

**Implemented:**
- JSON-LD schema.org markup (LocalBusiness, ContactPage, WebPage, FAQPage, AboutPage)
- Open Graph meta tags
- Twitter Card meta tags
- Canonical URLs
- Meta descriptions and keywords
- robots.txt and sitemap.xml (7 URLs)
- Semantic heading structure (H1-H4)

## Analytics & Conversion Tracking Status

| Tracking | Status | Installed |
|----------|--------|-----------|
| Google Ads Tag (gtag.js) | INSTALLED | 2026-03-23, all 7 pages, AW-18034797214 |
| Quote Form Conversion | INSTALLED | 2026-03-23, fires on form submit, $50 value |
| Phone Call Click Tracking | INSTALLED | 2026-03-23, fires on `tel:` click, $25 value |
| Email Click Tracking | INSTALLED | 2026-03-23, fires on `mailto:` click, $10 value |
| Google Analytics (GA4) | NOT installed | — |
| Google Tag Manager | NOT installed | — |
| Meta/Facebook Pixel | NOT installed | Needed for Meta Ads (future) |

**Form behavior:** Quote form uses mailto: fallback + fires Google Ads conversion event.

**Changelog:** All tracking changes documented in `frontend/changes-from-ads-lab-agent/`

### Still Needed

1. **Deploy to Cloudflare Pages** — tracking is in dev files, needs to be pushed to production
2. **UTM parameter handling** — site should preserve UTM params or pass them to the form
3. **GA4 setup** — for detailed analytics beyond Google Ads conversions

## Theme / Brand Colors

```json
{
  "primary": "#006657",       // Dark teal
  "primaryDim": "#004d42",    // Darker teal
  "bg": "#ffffff",            // White
  "bg2": "#f8f9fa",
  "text": "#1a1a2e",
  "accent": "#006657"
}
```

## Instance Relationship

```
AeroCore Lab (launcher: port 9200)
├── AeroCore Instance (port 9210 backend / 9280 frontend)
│   └── Manages: website, frontend, content, SEO
│   └── Deploys to: Cloudflare Pages (areocore.com)
│
└── AeroCore Ads Instance (port 9211 — THIS INSTANCE)
    └── Manages: paid advertising, campaigns, analytics
    └── References: the frontend for landing pages
    └── Needs: conversion tracking installed on frontend
```

---

## Revision History

| Date | Change |
|------|--------|
| 2026-03-23 | Initial documentation — site deployed on Cloudflare Pages, no tracking installed |
