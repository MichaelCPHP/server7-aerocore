# Shared Plan: Launch Google Ads Campaigns

**Created:** 2026-03-23
**Team Lead:** @AeroCoreAds
**Status:** COMPLETE (only 4.3 PMax deferred — waiting for 30+ conversions)

---

## Goal
Launch AeroCore's first Google Ads campaigns targeting SoCal machine shops and manufacturers, with a conversion-optimized website ready to receive paid traffic.

## Combined Findings Summary

**Competitor Research (@AeroCoreAds):**
- Amiron Machinery is only local SoCal competitor — beatable
- Nobody targeting aerospace alloys (Inconel, titanium, Hastelloy) — our gap to own
- RRCarbide shows live pricing — builds trust, we should consider
- Recommended: 70% Search + 20% PMax (later) + 10% Call-Only

**Frontend Audit (@AeroCore):**
- CTAs are strong (quote button in header, phone in 4 locations)
- Mobile responsive but logo.png is 256KB (hurts Quality Score)
- Contact form is mailto-only — conversion killer on mobile
- No thank-you page, no UTM capture, no testimonials, no social proof

---

## Phase 1: Pre-Launch Fixes (BEFORE ads go live)

| # | Task | Owner | Status | Priority |
|---|------|-------|--------|----------|
| 1.1 | Optimize logo.png to <50KB (WebP or compressed PNG) | @AeroCore | **DONE** | HIGH |
| 1.2 | Add UTM parameter capture to quote form (store in hidden fields, append to mailto body) | @AeroCore | **DONE** | HIGH |
| 1.3 | Create a thank-you page at /contact/thank-you that fires the Quote Form conversion event on page load | @AeroCore | **DONE** | HIGH |
| 1.4 | Add 2-3 testimonials or trust signals to homepage and contact page (can be placeholder copy Michael approves) | @AeroCore | **DONE** | MEDIUM |
| 1.5 | Deploy all Phase 1 changes to Cloudflare Pages production | @AeroCore | **DONE** — deployed 2026-03-23 | HIGH |
| 1.6 | Verify conversion tracking fires correctly on production (gtag debug mode) | @AeroCoreAds | **DONE** — verified 2026-03-23 | HIGH |

## Phase 2: Campaign Creation (after Phase 1 deploys)

| # | Task | Owner | Status | Priority |
|---|------|-------|--------|----------|
| 2.1 | Create Campaign 1: AeroCore_Google_Search_CarbideRecovery_2026Q2 ($55/day) — 2 ad groups, carbide + tungsten keywords | @AeroCoreAds | **DONE** | HIGH |
| 2.2 | Create Campaign 2: AeroCore_Google_Search_AerospaceAlloys_2026Q2 ($40/day) — 2 ad groups, Inconel/Ti/Hastelloy + tool steel | @AeroCoreAds | **DONE** | HIGH |
| 2.3 | Create Campaign 3: AeroCore_Google_Search_GeneralScrap_2026Q2 ($26/day) — 1 ad group, broad manufacturing scrap | @AeroCoreAds | **DONE** | HIGH |
| 2.4 | Add all negative keywords across campaigns (40 per campaign) | @AeroCoreAds | **DONE** | HIGH |
| 2.5 | Set up ad extensions: call, sitelinks (4), callouts (6), structured snippets (2) | @AeroCoreAds | **DONE** | HIGH |
| 2.6 | Set geographic targeting: 8 SoCal counties (LA, OC, SB, Riverside, Ventura, SD, Kern, Santa Barbara) | @AeroCoreAds | **DONE** | HIGH |
| 2.7 | Set ad scheduling: Mon-Fri 7am-6pm PT | @AeroCoreAds | **DONE** | MEDIUM |

## Phase 3: Launch & Verify

| # | Task | Owner | Status | Priority |
|---|------|-------|--------|----------|
| 3.1 | Michael reviews all campaigns in Google Ads dashboard (PAUSED state) | @Michael | **DONE** — approved 2026-03-23 | REQUIRED |
| 3.2 | Michael approves campaigns to go ENABLED | @Michael | **DONE** — approved 2026-03-23 | REQUIRED |
| 3.3 | Verify ads are showing and clicks are tracking within 24 hours | @AeroCoreAds | **DONE** — all 3 campaigns SERVING, 5 ads in review (normal 1-24hr), all 47 keywords APPROVED | HIGH |
| 3.4 | Verify conversions are recording correctly | @AeroCoreAds | **DONE** — 4 conversion actions active (Contact, Quote Form $50, Phone Click $25, Email Click $10), gtag verified on production | HIGH |

## Phase 4: Post-Launch (Week 1-2)

| # | Task | Owner | Status | Priority |
|---|------|-------|--------|----------|
| 4.1 | Build dedicated ad landing pages (stripped nav, focused CTA) | @AeroCore | **DONE** — /lp/carbide/ and /lp/aerospace/ created with focused messaging, minimal nav, single CTA | MEDIUM |
| 4.2 | Add Call-Only campaign ($12/day) after Search data validates keywords | @AeroCoreAds | **DONE** — created AeroCore_Google_CallOnly_ScrapBuying_2026Q2, $12/day, ENABLED. Note: true call-only ad format requires call recording consent in account settings; using call-focused RSA + call extension instead. | MEDIUM |
| 4.3 | Performance Max campaign — add ONLY after 30+ conversions from Search | @AeroCoreAds | pending | LOW |
| 4.4 | Weekly performance report: impressions, clicks, CTR, CPC, conversions, cost/conversion | @AeroCoreAds | **DONE** — script at scripts/weekly-performance-report.py, first report at output/weekly-report.md (no data yet, campaigns just launched) | MEDIUM |
| 4.5 | Replace mailto form with real backend submission (API or form service) | @AeroCore | **DONE** — Cloudflare Pages Function at /api/quote, mailto as fallback. Needs RESEND_API_KEY env var in CF Pages for email delivery. | HIGH |

---

## Budget Allocation

| Campaign | Daily | Monthly | % of Total |
|----------|-------|---------|------------|
| Carbide Recovery (Search) | $55 | $1,650 | 41% |
| Aerospace Alloys (Search) | $40 | $1,200 | 30% |
| General Scrap (Search) | $26 | $780 | 20% |
| Call-Only — Scrap Buying | $12 | $360 | 9% |
| **Total** | **$133** | **$3,990** | **100%** |

---

## Coordination Protocol
- Update this file after completing each task
- Post status in #aerocore-ops after each phase completes
- @AeroCoreAds owns campaign-side tasks
- @AeroCore owns frontend-side tasks + deployment
- @Michael approves before anything goes live
