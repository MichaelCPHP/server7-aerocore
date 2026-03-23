"""
Create all 3 Google Ads Search campaigns for AeroCore Q2 2026 via REST API.
All campaigns are created in PAUSED state.
Handles partial runs gracefully — skips already-created resources.
"""

import json
import yaml
import google.auth.transport.requests
from google.oauth2.credentials import Credentials
import requests as req

YAML_PATH = "env/google-ads.yaml"
PLAN_PATH = "/Volumes/T9 Drive 1/SERVER7-AEROCORE/aerocore-lab/instances/aerocore-ads/data/google-ads-campaign-plan.json"

# Load credentials
with open(YAML_PATH) as f:
    creds = yaml.safe_load(f)

CUSTOMER_ID = str(creds["customer_id"]).replace("-", "")
DEV_TOKEN = creds["developer_token"]

# Load campaign plan
with open(PLAN_PATH) as f:
    plan = json.load(f)

# Get OAuth access token
oauth_creds = Credentials(
    token=None,
    refresh_token=creds["refresh_token"],
    client_id=creds["client_id"],
    client_secret=creds["client_secret"],
    token_uri="https://oauth2.googleapis.com/token",
)
oauth_creds.refresh(google.auth.transport.requests.Request())
ACCESS_TOKEN = oauth_creds.token

BASE_URL = f"https://googleads.googleapis.com/v20/customers/{CUSTOMER_ID}"
HEADERS = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "developer-token": DEV_TOKEN,
    "Content-Type": "application/json",
}

# RSA limits
HEADLINE_MAX = 30
DESCRIPTION_MAX = 90
PATH_MAX = 15

# Fix path fields that exceed 15 char limit
PATH_OVERRIDES = {
    "aerospace-alloys": "alloys",
    "scrap-carbide": "scrap-carbide",
    "tungsten": "tungsten",
    "tool-steel": "tool-steel",
    "scrap": "scrap",
    "sell": "sell",
}

# Shortened descriptions that fit within 90 chars (per ad group)
FIXED_DESCRIPTIONS = {
    "Scrap Carbide Buying": [
        "We buy scrap carbide end mills, inserts, drills & rounds. Fast quotes, SoCal pickup.",
        "AreoCore pays top dollar for used carbide tooling. Professional material recovery.",
        "Serving LA, Orange County & Inland Empire. Get a fast quote on your scrap carbide.",
        "Don't toss valuable carbide. Competitive prices and reliable pickup. Call today!",
    ],
    "Tungsten Scrap Buying": [
        "AreoCore buys tungsten carbide, solids, powder & scrap. Fast SoCal pickup service.",
        "Professional tungsten recovery for machine shops. Transparent, market-rate pricing.",
        "Top dollar for tungsten scrap. Consistent pickups across LA, OC & Inland Empire.",
        "Stop stockpiling tungsten scrap. Fast quotes, reliable pickup. Call or quote online.",
    ],
    "Inconel & Titanium Scrap": [
        "We buy Inconel, titanium, Hastelloy & high-temp alloy scrap. SoCal pickup service.",
        "Aerospace manufacturers trust AreoCore. We buy Inconel 718, 625 & titanium scrap.",
        "Top dollar for aerospace alloy scrap. Serving defense contractors across SoCal.",
        "High-value alloy recovery. Fast quotes, competitive rates for Inconel, Ti & more.",
    ],
    "Tool Steel & HSS Scrap": [
        "AreoCore buys H13, D2, M2, HSS and other tool steel scrap. SoCal pickup service.",
        "Professional tool steel recovery for manufacturers. Transparent pricing, fast pickup.",
        "Top dollar for tool steel & HSS scrap. Serving LA, OC & the Inland Empire.",
        "We pay top dollar for tool steel scrap. Fast quote from AreoCore. Call today!",
    ],
    "General Manufacturing Scrap": [
        "AreoCore buys carbide, tungsten, Inconel, titanium & tool steel. SoCal manufacturers.",
        "Professional material recovery for CNC shops & manufacturers. Competitive pricing.",
        "Turn manufacturing scrap into cash. Free quotes, on-site pickup across SoCal.",
        "Machine shops trust AreoCore for reliable scrap pickup. Carbide, alloys & more.",
    ],
}


def search_stream(query):
    url = f"{BASE_URL}/googleAds:searchStream"
    resp = req.post(url, headers=HEADERS, json={"query": query})
    resp.raise_for_status()
    results = []
    for batch in resp.json():
        results.extend(batch.get("results", []))
    return results


def mutate(service, operations):
    url = f"{BASE_URL}/{service}:mutate"
    resp = req.post(url, headers=HEADERS, json={"operations": operations})
    if resp.status_code != 200:
        print(f"  ERROR ({resp.status_code}): {resp.text[:2000]}")
        resp.raise_for_status()
    return resp.json()


def find_campaign(name):
    results = search_stream(
        f"SELECT campaign.resource_name FROM campaign "
        f"WHERE campaign.name = '{name}' AND campaign.status != 'REMOVED'"
    )
    return results[0]["campaign"]["resourceName"] if results else None


def find_ad_group(campaign_rn, name):
    campaign_id = campaign_rn.split("/")[-1]
    results = search_stream(
        f"SELECT ad_group.resource_name FROM ad_group "
        f"WHERE ad_group.campaign = '{campaign_rn}' AND ad_group.name = '{name}'"
    )
    return results[0]["adGroup"]["resourceName"] if results else None


def find_ad_group_ads(ag_rn):
    results = search_stream(
        f"SELECT ad_group_ad.resource_name FROM ad_group_ad "
        f"WHERE ad_group_ad.ad_group = '{ag_rn}'"
    )
    return len(results)


def find_or_create_budget(name, daily_micros):
    results = search_stream(
        f"SELECT campaign_budget.resource_name FROM campaign_budget "
        f"WHERE campaign_budget.name = '{name}'"
    )
    if results:
        rn = results[0]["campaignBudget"]["resourceName"]
        print(f"  Reusing budget: {name}")
        return rn

    result = mutate("campaignBudgets", [
        {"create": {"name": name, "amountMicros": str(daily_micros), "deliveryMethod": "STANDARD"}}
    ])
    rn = result["results"][0]["resourceName"]
    print(f"  Created budget: {name} (${daily_micros / 1_000_000}/day)")
    return rn


def create_campaign(campaign_data, budget_rn):
    existing = find_campaign(campaign_data["name"])
    if existing:
        print(f"  Campaign already exists: {campaign_data['name']}")
        return existing

    result = mutate("campaigns", [{
        "create": {
            "name": campaign_data["name"],
            "status": "PAUSED",
            "advertisingChannelType": "SEARCH",
            "campaignBudget": budget_rn,
            "containsEuPoliticalAdvertising": "DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING",
            "targetSpend": {"cpcBidCeilingMicros": "10000000"},
            "networkSettings": {
                "targetGoogleSearch": True,
                "targetSearchNetwork": True,
                "targetContentNetwork": False,
            },
            "startDate": "2026-04-01",
            "trackingUrlTemplate": (
                "{lpurl}?utm_source=google&utm_medium=cpc"
                "&utm_campaign={campaignid}&utm_content={creative}&utm_term={keyword}"
            ),
        }
    }])
    rn = result["results"][0]["resourceName"]
    print(f"  Created campaign: {campaign_data['name']} [PAUSED]")
    return rn


def create_ad_group(campaign_rn, ag_data):
    existing = find_ad_group(campaign_rn, ag_data["name"])
    if existing:
        print(f"    Ad group already exists: {ag_data['name']}")
        return existing

    result = mutate("adGroups", [{
        "create": {
            "name": ag_data["name"],
            "campaign": campaign_rn,
            "status": "ENABLED",
            "type": "SEARCH_STANDARD",
            "cpcBidMicros": "5000000",
        }
    }])
    rn = result["results"][0]["resourceName"]
    print(f"    Created ad group: {ag_data['name']}")
    return rn


def add_keywords(ag_rn, keywords):
    # Check if keywords already exist
    existing = search_stream(
        f"SELECT ad_group_criterion.resource_name FROM ad_group_criterion "
        f"WHERE ad_group_criterion.ad_group = '{ag_rn}' "
        f"AND ad_group_criterion.type = 'KEYWORD'"
    )
    if existing:
        print(f"      Keywords already exist ({len(existing)} found), skipping")
        return

    match_map = {"exact": "EXACT", "phrase": "PHRASE", "broad": "BROAD"}
    operations = [{
        "create": {
            "adGroup": ag_rn,
            "status": "ENABLED",
            "keyword": {"text": kw["keyword"], "matchType": match_map[kw["match"]]},
        }
    } for kw in keywords]
    result = mutate("adGroupCriteria", operations)
    print(f"      Added {len(result['results'])} keywords")


def create_responsive_search_ad(ag_rn, ad_data, ag_name):
    # Check if ad already exists
    if find_ad_group_ads(ag_rn) > 0:
        print(f"      RSA already exists, skipping")
        return

    # Use fixed descriptions (properly sized)
    descriptions = FIXED_DESCRIPTIONS.get(ag_name, ad_data["descriptions"][:4])

    # Validate lengths and filter out policy-violating headlines
    headlines = []
    for h in ad_data["headlines"][:15]:
        # Remove headlines containing phone numbers (policy violation)
        if any(c.isdigit() for c in h) and ("(" in h or "-" in h):
            continue
        # Remove em dashes (can cause encoding issues)
        h = h.replace("\u2014", "-").replace("\u2013", "-")
        if len(h) > HEADLINE_MAX:
            h = h[:HEADLINE_MAX]
        headlines.append({"text": h})
    # Ensure we have at least 3 headlines (API minimum)
    if len(headlines) < 3:
        headlines.extend([{"text": "Get a Quote Today"}])

    desc_assets = []
    for d in descriptions:
        if len(d) > DESCRIPTION_MAX:
            d = d[:DESCRIPTION_MAX - 1] + "."
        desc_assets.append({"text": d})

    ad_body = {
        "adGroup": ag_rn,
        "status": "ENABLED",
        "ad": {
            "finalUrls": [ad_data["finalUrl"]],
            "responsiveSearchAd": {
                "headlines": headlines,
                "descriptions": desc_assets,
            },
        },
    }
    if ad_data.get("pathFields"):
        rsa = ad_body["ad"]["responsiveSearchAd"]
        # Path fields max 15 chars each
        if len(ad_data["pathFields"]) > 0:
            p1 = PATH_OVERRIDES.get(ad_data["pathFields"][0], ad_data["pathFields"][0])[:PATH_MAX]
            rsa["path1"] = p1
        if len(ad_data["pathFields"]) > 1:
            p2 = PATH_OVERRIDES.get(ad_data["pathFields"][1], ad_data["pathFields"][1])[:PATH_MAX]
            rsa["path2"] = p2

    result = mutate("adGroupAds", [{"create": ad_body}])
    print(f"      Created RSA")


def add_campaign_negative_keywords(campaign_rn, neg_keywords):
    existing = search_stream(
        f"SELECT campaign_criterion.resource_name FROM campaign_criterion "
        f"WHERE campaign_criterion.campaign = '{campaign_rn}' "
        f"AND campaign_criterion.negative = TRUE"
    )
    if existing:
        print(f"    Negative keywords already exist ({len(existing)} found), skipping")
        return

    operations = [{
        "create": {
            "campaign": campaign_rn,
            "negative": True,
            "keyword": {"text": nk, "matchType": "PHRASE"},
        }
    } for nk in neg_keywords]
    result = mutate("campaignCriteria", operations)
    print(f"    Added {len(result['results'])} negative keywords")


def main():
    print("=" * 60)
    print("AeroCore Google Ads Campaign Creator (REST API)")
    print("All campaigns created in PAUSED state")
    print("=" * 60)

    created_campaigns = []
    campaign_rns = []

    for campaign_data in plan["campaigns"]:
        print(f"\n--- {campaign_data['name']} ---")

        budget_rn = find_or_create_budget(
            f"{campaign_data['name']}_Budget",
            int(campaign_data["dailyBudget"] * 1_000_000),
        )

        campaign_rn = create_campaign(campaign_data, budget_rn)
        campaign_rns.append(campaign_rn)
        created_campaigns.append({
            "name": campaign_data["name"],
            "resource_name": campaign_rn,
            "daily_budget": campaign_data["dailyBudget"],
        })

        neg_keywords = plan.get("negativeKeywords", {}).get("campaignLevel", [])
        if neg_keywords:
            add_campaign_negative_keywords(campaign_rn, neg_keywords)

        for ag_data in campaign_data["adGroups"]:
            ag_rn = create_ad_group(campaign_rn, ag_data)
            add_keywords(ag_rn, ag_data["keywords"])
            for ad_data in ag_data["ads"]:
                create_responsive_search_ad(ag_rn, ad_data, ag_data["name"])

    print("\n" + "=" * 60)
    print("ALL CAMPAIGNS CREATED SUCCESSFULLY")
    print("=" * 60)
    total_daily = sum(c["daily_budget"] for c in created_campaigns)
    for c in created_campaigns:
        print(f"  {c['name']} — ${c['daily_budget']}/day [PAUSED]")
    print(f"\n  Total: ${total_daily}/day (${total_daily * 30}/mo)")
    print("\n  Michael must approve before enabling.")

    results_path = "/Volumes/T9 Drive 1/SERVER7-AEROCORE/aerocore-lab/instances/aerocore-ads/output/campaign-creation-results.json"
    with open(results_path, "w") as f:
        json.dump({"created": created_campaigns, "status": "all_paused", "campaign_resource_names": campaign_rns}, f, indent=2)
    print(f"\n  Results saved to output/campaign-creation-results.json")


if __name__ == "__main__":
    main()
