# AeroCore Ads — Paid Advertising Instance

Dedicated advertising operations platform for AeroCore Material Recovery.
Manages Google Ads and Meta Ads (Facebook + Instagram) campaigns.

## Instance Context

- **Server:** SERVER7-AEROCORE
- **Port:** 9211 (backend) / 9281 (frontend, when enabled)
- **Parent Platform:** AeroCore Lab (`/Volumes/T9 Drive 1/SERVER7-AEROCORE/aerocore-lab/`)
- **Main AeroCore site:** port 9280 (the `aerocore` instance frontend)
- **Launcher:** port 9200
- **MCP Servers:** `/Volumes/T9 Drive 1/SERVER7-AEROCORE/mcps/` (server-level, shared across instances)
- **MCP Registry:** `/Volumes/T9 Drive 1/SERVER7-AEROCORE/mcps/registry.json`

## Business Context

AeroCore Material Recovery purchases:
- Scrap carbide tooling (end mills, inserts, drills, rounds)
- High-performance alloys (Inconel, titanium, Hastelloy)
- Tungsten materials (carbide, solids, powder, scrap)
- Tool steel & HSS
- Aerospace components and surplus

**Target audiences for ads:**
- Machine shops and CNC operations
- Aerospace manufacturers and MRO facilities
- Defense contractors
- Tool & die shops
- Manufacturing plants with carbide/alloy scrap
- Surplus inventory holders

**Key value propositions to emphasize in ads:**
- Competitive pricing — we pay top dollar for scrap
- Fast turnaround — quick quotes and pickup
- Environmental sustainability — material recovery keeps materials out of landfills
- Expertise — we know aerospace-grade materials
- Nationwide service

## Ad Platform Integration

### Google Ads

**MCP Servers (ranked by recommendation):**

1. **promobase/google-ads-mcp** — Full read/write, 89 API v20 services, Python/FastMCP
   - GitHub: https://github.com/promobase/google-ads-mcp
   - Best for: Full campaign lifecycle management

2. **Google Official (read-only)** — Google's own MCP server, reporting/analytics only
   - GitHub: https://github.com/googleads/google-ads-mcp
   - Docs: https://developers.google.com/google-ads/api/docs/developer-toolkit/mcp-server
   - Best for: Safe performance reporting and analysis

3. **kLOsk/adloop** — Read + write with safety guardrails against accidental spend
   - GitHub: https://github.com/kLOsk/adloop
   - Best for: Managed write access with spend protection

4. **cohnen/mcp-google-ads** — Designed for Claude, natural language campaign management
   - GitHub: https://github.com/cohnen/mcp-google-ads

5. **TrueClicks/google-ads-mcp-js** — JavaScript, no developer token needed
   - GitHub: https://github.com/TrueClicks/google-ads-mcp-js
   - Best for: Quick setup without Google API credentials

**Authentication required:**
- Google Ads Developer Token (from API Center in a manager account)
- OAuth 2.0 credentials (client_id, client_secret, refresh_token)
- Customer ID (10-digit account ID)

**Node.js SDK:** `google-ads-api` (npm, by Opteo) — full GAQL support
**Python SDK:** `google-ads` (pip, official Google library)

**Query Language:** GAQL (Google Ads Query Language)
```sql
SELECT campaign.name, metrics.impressions, metrics.clicks, metrics.cost_micros
FROM campaign
WHERE segments.date DURING LAST_30_DAYS
ORDER BY metrics.impressions DESC
```

### Meta Ads (Facebook + Instagram)

**MCP Servers (ranked by recommendation):**

1. **pipeboard-co/meta-ads-mcp** — 30+ tools, most mature (636+ stars)
   - GitHub: https://github.com/pipeboard-co/meta-ads-mcp
   - Best for: Full campaign management + AI-powered analysis

2. **brijr/meta-mcp** — 25 tools, full CRUD lifecycle
   - GitHub: https://github.com/brijr/meta-mcp
   - Best for: Campaign create/read/update/delete operations

3. **attainmentlabs/meta-ads-mcp** — 5 focused tools, campaigns created PAUSED by default
   - GitHub: https://github.com/attainmentlabs/meta-ads-mcp
   - Best for: Safe campaign management, designed for Claude Code

4. **amekala/ads-mcp** — Multi-platform (Google + Meta + LinkedIn + TikTok), 100+ tools
   - GitHub: https://github.com/amekala/ads-mcp
   - Best for: Unified cross-platform ad management

5. **talknerdytome-labs/facebook-ads-library-mcp** — Competitive intelligence
   - GitHub: https://github.com/trypeggy/facebook-ads-library-mcp
   - Best for: Researching competitor ads in the public Ad Library

**Authentication required:**
- Meta Developer App
- Access Token (System User Token recommended for production)
- Ad Account ID
- Permissions: `ads_management`, `ads_read`, `business_management`

**Node.js SDK:** `facebook-nodejs-business-sdk` (npm, official Meta)
**Python SDK:** `facebook-python-business-sdk` (pip, official Meta)

## Multi-Platform MCP Option

**amekala/ads-mcp** covers both Google Ads AND Meta Ads in a single server with 100+ tools.
All campaigns created in paused state with write confirmation required.
GitHub: https://github.com/amekala/ads-mcp

## Safety Rules

1. **All campaigns MUST be created in PAUSED state** — never go live without human review
2. **Budget changes require explicit approval** — flag any spend increase recommendations
3. **Track all recommendations with ROI projections** — no blind spending
4. **Credential security** — never log or expose API tokens, store in environment variables only
5. **Test before scaling** — always start with small budgets and validate tracking before increasing spend

## Campaign Structure Standards

### Google Ads Campaign Naming Convention
```
[Business]_[Platform]_[CampaignType]_[Target]_[Date]
Example: AeroCore_Google_Search_CarbideBuying_2026Q1
```

### Meta Ads Campaign Naming Convention
```
[Business]_[Platform]_[Objective]_[Audience]_[Date]
Example: AeroCore_Meta_LeadGen_MachineShops_2026Q1
```

### UTM Parameter Standard
```
utm_source=google|facebook|instagram
utm_medium=cpc|cpm|social
utm_campaign={campaign_name}
utm_content={ad_variation}
utm_term={keyword} (Google only)
```

## Template Design

This instance is designed to be duplicated for other businesses across the server ecosystem.
When cloning for a new business:
1. Copy the `aerocore-ads` directory to a new instance name
2. Update `lab.json`: name, description, port, role (replace AeroCore business context)
3. Update `CLAUDE.md`: replace business context section
4. Keep all MCP/API references and safety rules as-is
5. Update campaign naming conventions with new business name

## Directory Structure

```
aerocore-ads/
  lab.json          — Instance configuration
  CLAUDE.md         — This file (agent instructions)
  data/             — Campaign data, keyword lists, audience definitions
  kb/               — Knowledge base and session history
  output/           — Generated reports, ad copy, campaign exports
  scripts/          — Automation scripts (reporting, bid management)
  docs/             — Platform guides, API setup instructions
```
