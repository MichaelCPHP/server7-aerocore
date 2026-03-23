# Meta Ads (Facebook + Instagram) Setup Guide

## Account Setup Checklist

1. Create or access a Meta Business Manager at https://business.facebook.com
2. Create a Facebook Page for AeroCore (if not existing)
3. Create a Meta Developer App at https://developers.facebook.com
4. Generate System User Token with ads_management permission
5. Set up Meta Pixel on the AeroCore website
6. Configure Conversions API (CAPI) for server-side tracking

## Authentication Credentials Needed

```
META_ACCESS_TOKEN=your_system_user_token
META_APP_SECRET=your_app_secret
META_AD_ACCOUNT_ID=act_123456789
META_PIXEL_ID=your_pixel_id
META_PAGE_ID=your_page_id
```

## Token Types

| Type | Duration | Use Case |
|------|----------|----------|
| Short-lived User Token | 1-2 hours | Testing only |
| Long-lived User Token | 60 days | Development |
| System User Token | Non-expiring (with Standard+ access) | Production |

## MCP Server Setup

### Option A: Pipeboard Meta Ads MCP (Most Mature)
```bash
git clone https://github.com/pipeboard-co/meta-ads-mcp
cd meta-ads-mcp
npm install
```

### Option B: Attainment Labs (Safe, Claude-Designed)
```bash
git clone https://github.com/attainmentlabs/meta-ads-mcp
cd meta-ads-mcp
pip install -r requirements.txt
```

### Option C: Unified Ads MCP (Google + Meta)
```bash
git clone https://github.com/amekala/ads-mcp
cd ads-mcp
npm install
```

## AeroCore Campaign Strategy

### Recommended Campaign Objectives

1. **Lead Generation** (primary)
   - In-platform lead forms for quick quote requests
   - Pre-filled fields reduce friction
   - Instant form with "Higher Intent" setting

2. **Traffic** (secondary)
   - Drive to AeroCore landing pages
   - Optimize for landing page views (not link clicks)

3. **Awareness** (brand building)
   - Broad reach to manufacturing/aerospace professionals
   - Video content showing material recovery process

### Audience Targeting for AeroCore

**Core Audiences:**
- Job titles: Machinist, CNC Operator, Purchasing Manager, Maintenance Manager, Shop Foreman, Plant Manager
- Industries: Aerospace, Manufacturing, Machine Shops, Defense, Automotive
- Interests: CNC machining, metalworking, aerospace manufacturing, industrial tools

**Custom Audiences:**
- Website visitors (via Meta Pixel)
- Quote form submitters (for exclusion/lookalike)
- Email list upload (existing contacts)

**Lookalike Audiences:**
- 1% lookalike of quote submitters (best quality)
- 1-3% lookalike of website visitors
- 1% lookalike of email list

### Ad Creative Guidelines

**Image Ads:**
- Show actual scrap carbide, tungsten, and alloy materials
- Use before/after or process imagery
- Include pricing signals ("We Pay Top Dollar")
- Clean, professional B2B aesthetic

**Video Ads (15-30 seconds):**
- Show the pickup/evaluation process
- Customer testimonials from machine shops
- "How it works" explainer

**Ad Copy Templates:**

*Lead Gen:*
> Sitting on scrap carbide? We pay top dollar for used end mills, inserts, and carbide tooling. Get a quote in minutes.
> [Get Your Free Quote]

*Awareness:*
> AeroCore Material Recovery turns your scrap into cash. We buy Inconel, titanium, Hastelloy, carbide, and more from shops nationwide.
> [Learn More]

*Retargeting:*
> Still have that scrap sitting around? AeroCore makes it easy -- free shipping, fast quotes, and competitive prices.
> [Get Your Quote Now]

### Placement Strategy
- **Facebook Feed** — primary placement for lead gen
- **Instagram Feed** — visual-heavy content
- **Facebook Marketplace** — relevant for B2B material selling
- **Audience Network** — extend reach at lower CPM
- **Automatic Placements** recommended initially, optimize later

### Budget Recommendations
- Start with $30-50/day per campaign
- Run for 7 days before making optimization decisions
- Let Meta's learning phase complete (50 conversions per ad set)
- Scale winning ad sets by duplicating, not increasing budget

### Meta Pixel Events to Track
- PageView (automatic)
- Lead (quote form submission)
- Contact (phone/email click)
- ViewContent (materials/pricing pages)
- Custom: QuoteRequest, MaterialInquiry

### Conversions API (CAPI)
Server-side event tracking that works alongside the Pixel:
- Bypasses ad blockers and iOS ATT restrictions
- Sends events from AeroCore's backend directly to Meta
- Requires: Pixel ID, Access Token, event data (email hash, phone hash, event name)
- Deduplicate with browser Pixel using event_id parameter
