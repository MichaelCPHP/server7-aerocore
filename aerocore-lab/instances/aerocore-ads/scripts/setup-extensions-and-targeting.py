"""
Set up ad extensions (assets), geographic targeting, and ad scheduling
for all AeroCore campaigns via REST API.
"""

import json
import yaml
import google.auth.transport.requests
from google.oauth2.credentials import Credentials
import requests as req

YAML_PATH = "env/google-ads.yaml"

with open(YAML_PATH) as f:
    creds = yaml.safe_load(f)

CUSTOMER_ID = str(creds["customer_id"]).replace("-", "")
DEV_TOKEN = creds["developer_token"]

# Load campaign results
RESULTS_PATH = "/Volumes/T9 Drive 1/SERVER7-AEROCORE/aerocore-lab/instances/aerocore-ads/output/campaign-creation-results.json"
with open(RESULTS_PATH) as f:
    results = json.load(f)

CAMPAIGN_RNS = results["campaign_resource_names"]

# Auth
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
        print(f"  ERROR ({resp.status_code}): {resp.text[:1500]}")
        return None
    return resp.json()


# ============================================================
# 1. GEOGRAPHIC TARGETING
# ============================================================
def setup_geo_targeting():
    """Add SoCal county targeting to all campaigns."""
    print("\n--- Geographic Targeting ---")

    # Google Ads geo target constants for SoCal counties
    # These are official Google criteria IDs
    COUNTY_TARGETS = {
        "Los Angeles County": 9057137,
        "Orange County": 1014091,
        "San Bernardino County": 9057153,
        "Riverside County": 9057150,
        "Ventura County": 9057173,
        "San Diego County": 9057154,
        "Kern County": 9057133,
        "Santa Barbara County": 9057159,
    }

    for campaign_rn in CAMPAIGN_RNS:
        campaign_name = campaign_rn.split("/")[-1]

        # Check if geo targeting already exists
        existing = search_stream(
            f"SELECT campaign_criterion.resource_name FROM campaign_criterion "
            f"WHERE campaign_criterion.campaign = '{campaign_rn}' "
            f"AND campaign_criterion.type = 'LOCATION'"
        )
        if existing:
            print(f"  Geo targeting already set for campaign {campaign_name} ({len(existing)} locations)")
            continue

        operations = []
        for county_name, criteria_id in COUNTY_TARGETS.items():
            operations.append({
                "create": {
                    "campaign": campaign_rn,
                    "location": {
                        "geoTargetConstant": f"geoTargetConstants/{criteria_id}",
                    },
                }
            })

        result = mutate("campaignCriteria", operations)
        if result:
            print(f"  Added {len(result['results'])} county targets to campaign {campaign_name}")


# ============================================================
# 2. AD SCHEDULING
# ============================================================
def setup_ad_scheduling():
    """Set Mon-Fri 7am-6pm PT for all campaigns."""
    print("\n--- Ad Scheduling ---")

    # Days: MONDAY=2, TUESDAY=3, WEDNESDAY=4, THURSDAY=5, FRIDAY=6
    WEEKDAYS = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY"]

    for campaign_rn in CAMPAIGN_RNS:
        campaign_name = campaign_rn.split("/")[-1]

        # Check if scheduling already exists
        existing = search_stream(
            f"SELECT campaign_criterion.resource_name FROM campaign_criterion "
            f"WHERE campaign_criterion.campaign = '{campaign_rn}' "
            f"AND campaign_criterion.type = 'AD_SCHEDULE'"
        )
        if existing:
            print(f"  Ad schedule already set for campaign {campaign_name}")
            continue

        operations = []
        for day in WEEKDAYS:
            operations.append({
                "create": {
                    "campaign": campaign_rn,
                    "adSchedule": {
                        "dayOfWeek": day,
                        "startHour": 7,
                        "startMinute": "ZERO",
                        "endHour": 18,
                        "endMinute": "ZERO",
                    },
                }
            })

        result = mutate("campaignCriteria", operations)
        if result:
            print(f"  Set M-F 7am-6pm schedule for campaign {campaign_name}")


# ============================================================
# 3. AD EXTENSIONS (Assets)
# ============================================================
def create_asset(asset_data):
    """Create an asset and return its resource name."""
    result = mutate("assets", [{"create": asset_data}])
    if result:
        return result["results"][0]["resourceName"]
    return None


def link_asset_to_campaign(campaign_rn, asset_rn, field_type):
    """Link an asset to a campaign."""
    result = mutate("campaignAssets", [{
        "create": {
            "campaign": campaign_rn,
            "asset": asset_rn,
            "fieldType": field_type,
        }
    }])
    return result is not None


def setup_call_extension():
    """Create and link call asset to all campaigns."""
    print("\n--- Call Extension ---")

    # Check if call asset already exists
    existing = search_stream(
        "SELECT asset.resource_name, asset.call_asset.phone_number "
        "FROM asset WHERE asset.type = 'CALL'"
    )
    if existing:
        asset_rn = existing[0]["asset"]["resourceName"]
        print(f"  Call asset already exists: {asset_rn}")
    else:
        asset_rn = create_asset({
            "callAsset": {
                "countryCode": "US",
                "phoneNumber": "9492398912",
                "callConversionReportingState": "USE_ACCOUNT_LEVEL_CALL_CONVERSION_ACTION",
            }
        })
        if asset_rn:
            print(f"  Created call asset: {asset_rn}")
        else:
            print("  Failed to create call asset")
            return

    for campaign_rn in CAMPAIGN_RNS:
        # Check if already linked
        campaign_id = campaign_rn.split("/")[-1]
        existing_links = search_stream(
            f"SELECT campaign_asset.resource_name FROM campaign_asset "
            f"WHERE campaign_asset.campaign = '{campaign_rn}' "
            f"AND campaign_asset.field_type = 'CALL'"
        )
        if existing_links:
            print(f"  Call already linked to campaign {campaign_id}")
            continue

        if link_asset_to_campaign(campaign_rn, asset_rn, "CALL"):
            print(f"  Linked call to campaign {campaign_id}")


def setup_sitelink_extensions():
    """Create and link sitelink assets to all campaigns."""
    print("\n--- Sitelink Extensions ---")

    sitelinks = [
        {
            "sitelinkAsset": {
                "linkText": "Get a Free Quote",
                "description1": "Fast quotes on carbide & alloys",
                "description2": "Competitive pricing, fast pickup",
            },
            "finalUrls": ["https://aerocore.pages.dev/contact"],
        },
        {
            "sitelinkAsset": {
                "linkText": "Materials We Buy",
                "description1": "Carbide, tungsten, Inconel, Ti",
                "description2": "Tool steel, HSS & alloys",
            },
            "finalUrls": ["https://aerocore.pages.dev/materials"],
        },
        {
            "sitelinkAsset": {
                "linkText": "Our Process",
                "description1": "Simple 3-step process",
                "description2": "Quote, pickup, payment",
            },
            "finalUrls": ["https://aerocore.pages.dev/process"],
        },
        {
            "sitelinkAsset": {
                "linkText": "Service Areas",
                "description1": "Serving all of SoCal",
                "description2": "LA, OC, Inland Empire & more",
            },
            "finalUrls": ["https://aerocore.pages.dev/about"],
        },
    ]

    # Check existing sitelink assets
    existing = search_stream(
        "SELECT asset.resource_name FROM asset WHERE asset.type = 'SITELINK'"
    )
    if existing and len(existing) >= 4:
        print(f"  Sitelink assets already exist ({len(existing)} found)")
        asset_rns = [e["asset"]["resourceName"] for e in existing]
    else:
        asset_rns = []
        for sl in sitelinks:
            rn = create_asset(sl)
            if rn:
                asset_rns.append(rn)
                print(f"  Created sitelink: {sl['sitelinkAsset']['linkText']}")

    for campaign_rn in CAMPAIGN_RNS:
        campaign_id = campaign_rn.split("/")[-1]
        existing_links = search_stream(
            f"SELECT campaign_asset.resource_name FROM campaign_asset "
            f"WHERE campaign_asset.campaign = '{campaign_rn}' "
            f"AND campaign_asset.field_type = 'SITELINK'"
        )
        if existing_links:
            print(f"  Sitelinks already linked to campaign {campaign_id}")
            continue

        for asset_rn in asset_rns:
            link_asset_to_campaign(campaign_rn, asset_rn, "SITELINK")
        print(f"  Linked {len(asset_rns)} sitelinks to campaign {campaign_id}")


def setup_callout_extensions():
    """Create and link callout assets to all campaigns."""
    print("\n--- Callout Extensions ---")

    callouts = [
        "Free On-Site Pickup",
        "Same-Week Service",
        "Competitive Prices",
        "Transparent Pricing",
        "Serving All of SoCal",
        "Professional Service",
    ]

    existing = search_stream(
        "SELECT asset.resource_name FROM asset WHERE asset.type = 'CALLOUT'"
    )
    if existing and len(existing) >= 6:
        print(f"  Callout assets already exist ({len(existing)} found)")
        asset_rns = [e["asset"]["resourceName"] for e in existing]
    else:
        asset_rns = []
        for co in callouts:
            rn = create_asset({"calloutAsset": {"calloutText": co}})
            if rn:
                asset_rns.append(rn)
        print(f"  Created {len(asset_rns)} callout assets")

    for campaign_rn in CAMPAIGN_RNS:
        campaign_id = campaign_rn.split("/")[-1]
        existing_links = search_stream(
            f"SELECT campaign_asset.resource_name FROM campaign_asset "
            f"WHERE campaign_asset.campaign = '{campaign_rn}' "
            f"AND campaign_asset.field_type = 'CALLOUT'"
        )
        if existing_links:
            print(f"  Callouts already linked to campaign {campaign_id}")
            continue

        for asset_rn in asset_rns:
            link_asset_to_campaign(campaign_rn, asset_rn, "CALLOUT")
        print(f"  Linked {len(asset_rns)} callouts to campaign {campaign_id}")


def setup_structured_snippets():
    """Create and link structured snippet assets to all campaigns."""
    print("\n--- Structured Snippets ---")

    snippets = [
        {
            "structuredSnippetAsset": {
                "header": "Types",
                "values": ["Carbide End Mills", "Carbide Inserts", "Tungsten", "Inconel", "Titanium", "Tool Steel", "HSS"],
            }
        },
        {
            "structuredSnippetAsset": {
                "header": "Service catalog",
                "values": ["Scrap Pickup", "Material Quotes", "On-Site Assessment", "Recurring Pickup", "Bulk Processing"],
            }
        },
    ]

    existing = search_stream(
        "SELECT asset.resource_name FROM asset WHERE asset.type = 'STRUCTURED_SNIPPET'"
    )
    if existing and len(existing) >= 2:
        print(f"  Snippet assets already exist ({len(existing)} found)")
        asset_rns = [e["asset"]["resourceName"] for e in existing]
    else:
        asset_rns = []
        for sn in snippets:
            rn = create_asset(sn)
            if rn:
                asset_rns.append(rn)
                print(f"  Created snippet: {sn['structuredSnippetAsset']['header']}")

    for campaign_rn in CAMPAIGN_RNS:
        campaign_id = campaign_rn.split("/")[-1]
        existing_links = search_stream(
            f"SELECT campaign_asset.resource_name FROM campaign_asset "
            f"WHERE campaign_asset.campaign = '{campaign_rn}' "
            f"AND campaign_asset.field_type = 'STRUCTURED_SNIPPET'"
        )
        if existing_links:
            print(f"  Snippets already linked to campaign {campaign_id}")
            continue

        for asset_rn in asset_rns:
            link_asset_to_campaign(campaign_rn, asset_rn, "STRUCTURED_SNIPPET")
        print(f"  Linked {len(asset_rns)} snippets to campaign {campaign_id}")


def main():
    print("=" * 60)
    print("AeroCore Google Ads — Extensions, Targeting & Scheduling")
    print("=" * 60)
    print(f"Configuring {len(CAMPAIGN_RNS)} campaigns")

    setup_geo_targeting()
    setup_ad_scheduling()
    setup_call_extension()
    setup_sitelink_extensions()
    setup_callout_extensions()
    setup_structured_snippets()

    print("\n" + "=" * 60)
    print("SETUP COMPLETE")
    print("=" * 60)
    print("  - Geographic targeting: 8 SoCal counties")
    print("  - Ad scheduling: Mon-Fri 7am-6pm PT")
    print("  - Call extension: (949) 239-8912")
    print("  - Sitelinks: 4 links")
    print("  - Callouts: 6 callouts")
    print("  - Structured snippets: 2 snippets")


if __name__ == "__main__":
    main()
