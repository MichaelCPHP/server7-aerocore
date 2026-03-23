# Google Ads Setup Guide

## Account Setup Checklist

1. Create or access a Google Ads account at https://ads.google.com
2. Create a Manager Account (MCC) if managing multiple accounts
3. Apply for API access via the API Center in the manager account
4. Generate OAuth 2.0 credentials via Google Cloud Console
5. Obtain Developer Token (starts as Test level, apply for Basic/Standard)

## Developer Token Access Levels

| Level | Scope | Limits |
|-------|-------|--------|
| Test | Test accounts only | Limited |
| Basic | Production, limited ops/day | Rate-limited |
| Standard | Full production | Requires Google review |

## Authentication Credentials Needed

```
GOOGLE_ADS_DEVELOPER_TOKEN=your_22_char_token
GOOGLE_ADS_CLIENT_ID=your_client_id.apps.googleusercontent.com
GOOGLE_ADS_CLIENT_SECRET=your_client_secret
GOOGLE_ADS_REFRESH_TOKEN=your_refresh_token
GOOGLE_ADS_CUSTOMER_ID=1234567890
GOOGLE_ADS_LOGIN_CUSTOMER_ID=0987654321  # if using manager account
```

## MCP Server Setup

### Option A: Official Google MCP (Read-Only)
```bash
git clone https://github.com/googleads/google-ads-mcp
cd google-ads-mcp
pip install -r requirements.txt
```

### Option B: Promobase Full Read/Write
```bash
git clone https://github.com/promobase/google-ads-mcp
cd google-ads-mcp
pip install -r requirements.txt
```

### Option C: Unified Ads MCP (Google + Meta)
```bash
git clone https://github.com/amekala/ads-mcp
cd ads-mcp
npm install
```

## AeroCore Campaign Strategy

### Recommended Campaign Types

1. **Search Campaigns** (highest intent)
   - "sell scrap carbide"
   - "scrap carbide buyer near me"
   - "sell tungsten scrap"
   - "aerospace alloy recycling"
   - "sell used end mills"

2. **Performance Max** (broad reach)
   - Feed-based campaigns using material categories
   - Automated bidding across Search, Display, YouTube, Gmail

3. **Display Remarketing** (re-engagement)
   - Target visitors who viewed pricing/quote pages but didn't convert

### Keyword Categories for AeroCore

**Carbide Keywords:**
- sell scrap carbide, scrap carbide buyer, carbide recycling
- used carbide end mills, carbide insert scrap, carbide round scrap
- carbide tooling buyer, scrap carbide price per pound

**Tungsten Keywords:**
- sell tungsten scrap, tungsten recycling, tungsten carbide buyer
- scrap tungsten price, tungsten rod scrap

**Aerospace Alloy Keywords:**
- sell inconel scrap, titanium scrap buyer, hastelloy scrap
- aerospace alloy recycling, nickel alloy scrap buyer
- titanium bar scrap, inconel 718 scrap price

**General Keywords:**
- sell scrap metal, industrial scrap buyer, manufacturing scrap recycling
- tool steel scrap buyer, HSS scrap price

### Negative Keywords to Add
- "buy carbide" (we buy FROM people, not sell TO them)
- "carbide for sale" (we're the buyer)
- "new end mills", "new inserts" (we buy used/scrap)
- "tungsten rings", "tungsten jewelry" (wrong industry)

### Bidding Strategy Recommendations
- Start with Maximize Clicks to gather data (first 2-4 weeks)
- Switch to Target CPA once 30+ conversions accumulated
- Set daily budget at $50-100/campaign initially
- Scale winning campaigns by 20% increments weekly

### Conversion Tracking
- Primary: Quote form submissions
- Secondary: Phone calls (via call tracking)
- Secondary: Email clicks (mailto: tracking)
- Micro: Time on site > 2 min, 3+ pages viewed
