# Google Ads — Platform Configuration

**Last Updated:** 2026-03-23
**Status:** Active — API connected and verified

---

## Account Details

| Field | Value |
|-------|-------|
| Platform | Google Ads |
| Account Name | Areocore |
| Customer ID | 580-872-1896 |
| Account Owner | industrialrefiners@gmail.com |
| Manager Account (MCC) | 305-466-8019 |
| MCC Owner | standardasphaltpaving@gmail.com |
| MCC Linked to Account | No (not yet linked) |

## API Access

| Field | Value |
|-------|-------|
| Access Method | Google Ads API v20 (Python SDK) |
| Auth Type | OAuth 2.0 (Desktop App — user credentials) |
| Developer Token Access Level | Explorer Access |
| Developer Token Source | Manager Account (305-466-8019) |
| Google Cloud Project | AeroCore Ads (Project ID: 399441500369) |
| OAuth Authorized User | industrialrefiners@gmail.com |
| API Enabled | Google Ads API (googleads.googleapis.com) |

## Credential Locations

| Credential | Location |
|-----------|----------|
| YAML Config | `/Volumes/T9 Drive 1/SERVER7-AEROCORE/mcps/google-ads-mcp/env/google-ads.yaml` |
| .env File (backup) | `/Volumes/T9 Drive 1/SERVER7-AEROCORE/mcps/google-ads-mcp/.env` |
| OAuth Script | `instances/aerocore-ads/scripts/get-refresh-token.py` |

**Credentials stored in YAML config:**
- `developer_token` — from MCC API Center
- `client_id` — from Google Cloud Console OAuth 2.0 credentials
- `client_secret` — from Google Cloud Console OAuth 2.0 credentials
- `refresh_token` — generated via OAuth flow (authorized by industrialrefiners@gmail.com)
- `customer_id` — 5808721896 (no dashes)

## MCP Server

| Field | Value |
|-------|-------|
| Server | promobase/google-ads-mcp |
| Path | `/Volumes/T9 Drive 1/SERVER7-AEROCORE/mcps/google-ads-mcp/` |
| Runtime | Python (uv) |
| Status | Installed, credentials configured |
| Capabilities | Full read/write — 89 API v20 services (campaigns, ad groups, keywords, bidding, reporting) |
| SDK Client Modified | Yes — updated `src/sdk_client.py` to support OAuth2 user credentials (originally only supported service account) |

## How API Access Works

1. The **Developer Token** comes from the Manager Account (MCC) — this is required for any Google Ads API access regardless of auth method
2. The **OAuth credentials** (client_id, client_secret) come from the Google Cloud project "AeroCore Ads" created under standardasphaltpaving@gmail.com
3. The **Refresh Token** was authorized by **industrialrefiners@gmail.com** — this is the account that has direct permission to manage 580-872-1896
4. API calls go **directly to 580-872-1896** — we do NOT route through the Manager Account (the `login_customer_id` is commented out because the MCC is not linked to the AreoCore account yet)

## Important Notes

- The Developer Token is at **Explorer Access** level — this works on production accounts but has some rate limits. Apply for Basic Access via the API Center if rate limits become an issue.
- The OAuth consent screen is in **testing mode** — only test users (industrialrefiners@gmail.com, standardasphaltpaving@gmail.com) can authorize. If the refresh token expires, re-run `scripts/get-refresh-token.py`.
- The MCC (305-466-8019) and AreoCore account (580-872-1896) are on **different Gmail accounts** and are **not linked**. To link them in the future: send a link request from the MCC, accept it from the AreoCore account, then uncomment `login_customer_id` in the YAML config.

## Campaign Configuration

- Campaign plan: `instances/aerocore-ads/data/google-ads-campaign-plan.json`
- All campaigns created in **PAUSED** state
- Budget: $3,630/month ($121/day)
- Geographic targeting: Southern California (LA, OC, San Bernardino, Riverside, Ventura, San Diego, Kern, Santa Barbara counties)
- Bidding strategy: Maximize Clicks (switch to Target CPA after 30+ conversions)

## Troubleshooting Log

### 2026-03-23 — Initial Setup
- **Issue:** API Center only available on Manager Accounts — had to create MCC first
- **Issue:** MCC created on different Gmail (standardasphaltpaving) than the ads account (industrialrefiners)
- **Issue:** Google Ads API not enabled on Cloud project — had to enable on the correct project (399441500369)
- **Issue:** Permission denied when using `login_customer_id` — accounts not linked, removed MCC intermediary
- **Resolution:** Direct API access to 580-872-1896 using industrialrefiners OAuth token works

---

## Revision History

| Date | Change |
|------|--------|
| 2026-03-23 | Initial setup — account created, API connected, campaign plan built |
