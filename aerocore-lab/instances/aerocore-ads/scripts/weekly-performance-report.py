"""
AeroCore Google Ads — Weekly Performance Report
Generates a markdown report with key metrics for all active campaigns.
Run with: cd /Volumes/T9\ Drive\ 1/SERVER7-AEROCORE/mcps/google-ads-mcp && uv run python <path>
"""

import json
import yaml
from datetime import datetime, timedelta
import google.auth.transport.requests
from google.oauth2.credentials import Credentials
import requests as req

YAML_PATH = "env/google-ads.yaml"

with open(YAML_PATH) as f:
    creds = yaml.safe_load(f)

CUSTOMER_ID = str(creds["customer_id"]).replace("-", "")

oauth_creds = Credentials(
    token=None,
    refresh_token=creds["refresh_token"],
    client_id=creds["client_id"],
    client_secret=creds["client_secret"],
    token_uri="https://oauth2.googleapis.com/token",
)
oauth_creds.refresh(google.auth.transport.requests.Request())

HEADERS = {
    "Authorization": f"Bearer {oauth_creds.token}",
    "developer-token": creds["developer_token"],
    "Content-Type": "application/json",
}

BASE = f"https://googleads.googleapis.com/v20/customers/{CUSTOMER_ID}"


def query(q):
    resp = req.post(f"{BASE}/googleAds:searchStream", headers=HEADERS, json={"query": q})
    results = []
    if resp.status_code == 200:
        for batch in resp.json():
            results.extend(batch.get("results", []))
    return results


def fmt_currency(micros):
    if micros is None:
        return "$0.00"
    return f"${int(micros) / 1_000_000:,.2f}"


def fmt_pct(value):
    if value is None:
        return "0.00%"
    return f"{float(value) * 100:.2f}%"


def generate_report():
    today = datetime.now()
    week_ago = today - timedelta(days=7)
    date_from = week_ago.strftime("%Y-%m-%d")
    date_to = today.strftime("%Y-%m-%d")

    report = []
    report.append(f"# AeroCore Google Ads — Weekly Performance Report")
    report.append(f"**Period:** {date_from} to {date_to}")
    report.append(f"**Generated:** {today.strftime('%Y-%m-%d %H:%M PT')}")
    report.append(f"**Account:** 580-872-1896")
    report.append("")

    # === Account-level summary ===
    account_data = query(f"""
        SELECT metrics.impressions, metrics.clicks, metrics.cost_micros,
               metrics.conversions, metrics.cost_per_conversion,
               metrics.click_through_rate, metrics.average_cpc,
               metrics.conversions_value
        FROM customer
        WHERE segments.date BETWEEN '{date_from}' AND '{date_to}'
    """)

    report.append("## Account Summary")
    report.append("")
    if account_data:
        m = account_data[0].get("metrics", {})
        impressions = int(m.get("impressions", 0))
        clicks = int(m.get("clicks", 0))
        cost = int(m.get("costMicros", 0))
        conversions = float(m.get("conversions", 0))
        ctr = float(m.get("clickThroughRate", 0))
        avg_cpc = int(m.get("averageCpc", 0))
        cost_per_conv = int(m.get("costPerConversion", 0)) if m.get("costPerConversion") else 0
        conv_value = float(m.get("conversionsValue", 0))

        report.append("| Metric | Value |")
        report.append("|--------|-------|")
        report.append(f"| Impressions | {impressions:,} |")
        report.append(f"| Clicks | {clicks:,} |")
        report.append(f"| CTR | {ctr * 100:.2f}% |")
        report.append(f"| Avg CPC | {fmt_currency(avg_cpc)} |")
        report.append(f"| Total Spend | {fmt_currency(cost)} |")
        report.append(f"| Conversions | {conversions:.0f} |")
        report.append(f"| Cost/Conversion | {fmt_currency(cost_per_conv)} |")
        report.append(f"| Conversion Value | {fmt_currency(int(conv_value * 1_000_000))} |")
    else:
        report.append("*No data for this period yet.*")
    report.append("")

    # === Campaign-level breakdown ===
    report.append("## Campaign Performance")
    report.append("")
    campaign_data = query(f"""
        SELECT campaign.name, campaign.status, campaign.serving_status,
               metrics.impressions, metrics.clicks, metrics.cost_micros,
               metrics.conversions, metrics.click_through_rate, metrics.average_cpc,
               campaign_budget.amount_micros
        FROM campaign
        WHERE campaign.status != 'REMOVED'
        AND segments.date BETWEEN '{date_from}' AND '{date_to}'
        ORDER BY metrics.cost_micros DESC
    """)

    if campaign_data:
        report.append("| Campaign | Status | Impressions | Clicks | CTR | Avg CPC | Spend | Conv | Cost/Conv |")
        report.append("|----------|--------|-------------|--------|-----|---------|-------|------|-----------|")
        for row in campaign_data:
            c = row.get("campaign", {})
            m = row.get("metrics", {})
            name = c.get("name", "")
            status = c.get("servingStatus", c.get("status", ""))
            imp = int(m.get("impressions", 0))
            clk = int(m.get("clicks", 0))
            ctr = float(m.get("clickThroughRate", 0))
            cpc = int(m.get("averageCpc", 0))
            cost = int(m.get("costMicros", 0))
            conv = float(m.get("conversions", 0))
            cpc_conv = int(m.get("costPerConversion", 0)) if m.get("costPerConversion") else 0
            report.append(f"| {name} | {status} | {imp:,} | {clk:,} | {ctr*100:.1f}% | {fmt_currency(cpc)} | {fmt_currency(cost)} | {conv:.0f} | {fmt_currency(cpc_conv)} |")
    else:
        report.append("*No campaign data for this period yet.*")
    report.append("")

    # === Ad Group breakdown ===
    report.append("## Ad Group Performance")
    report.append("")
    ag_data = query(f"""
        SELECT ad_group.name, campaign.name,
               metrics.impressions, metrics.clicks, metrics.cost_micros,
               metrics.conversions, metrics.click_through_rate
        FROM ad_group
        WHERE campaign.status != 'REMOVED'
        AND segments.date BETWEEN '{date_from}' AND '{date_to}'
        ORDER BY metrics.cost_micros DESC
    """)

    if ag_data:
        report.append("| Ad Group | Campaign | Impr | Clicks | CTR | Spend | Conv |")
        report.append("|----------|----------|------|--------|-----|-------|------|")
        for row in ag_data:
            ag = row.get("adGroup", {})
            c = row.get("campaign", {})
            m = row.get("metrics", {})
            report.append(f"| {ag.get('name','')} | {c.get('name','')[:30]} | {int(m.get('impressions',0)):,} | {int(m.get('clicks',0)):,} | {float(m.get('clickThroughRate',0))*100:.1f}% | {fmt_currency(int(m.get('costMicros',0)))} | {float(m.get('conversions',0)):.0f} |")
    else:
        report.append("*No ad group data for this period yet.*")
    report.append("")

    # === Top keywords ===
    report.append("## Top Keywords (by clicks)")
    report.append("")
    kw_data = query(f"""
        SELECT ad_group_criterion.keyword.text, ad_group_criterion.keyword.match_type,
               metrics.impressions, metrics.clicks, metrics.cost_micros,
               metrics.conversions, metrics.click_through_rate
        FROM keyword_view
        WHERE campaign.status != 'REMOVED'
        AND segments.date BETWEEN '{date_from}' AND '{date_to}'
        ORDER BY metrics.clicks DESC
        LIMIT 15
    """)

    if kw_data:
        report.append("| Keyword | Match | Impr | Clicks | CTR | Spend | Conv |")
        report.append("|---------|-------|------|--------|-----|-------|------|")
        for row in kw_data:
            kw = row.get("adGroupCriterion", {}).get("keyword", {})
            m = row.get("metrics", {})
            report.append(f"| {kw.get('text','')} | {kw.get('matchType','')} | {int(m.get('impressions',0)):,} | {int(m.get('clicks',0)):,} | {float(m.get('clickThroughRate',0))*100:.1f}% | {fmt_currency(int(m.get('costMicros',0)))} | {float(m.get('conversions',0)):.0f} |")
    else:
        report.append("*No keyword data for this period yet.*")
    report.append("")

    # === Conversion actions ===
    report.append("## Conversion Tracking")
    report.append("")
    conv_data = query(f"""
        SELECT conversion_action.name,
               metrics.conversions, metrics.conversions_value, metrics.cost_per_conversion
        FROM conversion_action
        WHERE conversion_action.status = 'ENABLED'
        AND segments.date BETWEEN '{date_from}' AND '{date_to}'
    """)

    if conv_data:
        report.append("| Conversion Action | Conversions | Value | Cost/Conv |")
        report.append("|-------------------|-------------|-------|-----------|")
        for row in conv_data:
            ca = row.get("conversionAction", {})
            m = row.get("metrics", {})
            report.append(f"| {ca.get('name','')} | {float(m.get('conversions',0)):.0f} | {fmt_currency(int(float(m.get('conversionsValue',0)) * 1_000_000))} | {fmt_currency(int(m.get('costPerConversion',0)) if m.get('costPerConversion') else 0)} |")
    else:
        report.append("*No conversion data for this period yet — campaigns just launched.*")
    report.append("")

    # === Recommendations ===
    report.append("## Notes & Recommendations")
    report.append("")
    report.append("- Campaigns launched on 2026-03-23. Allow 1-2 weeks for data to accumulate.")
    report.append("- Bidding strategy: Maximize Clicks. Switch to Target CPA after 30+ conversions.")
    report.append("- Monitor search terms report weekly for new negative keyword opportunities.")
    report.append("- Review ad approval status — new ads take 1-24 hours for Google review.")
    report.append("")
    report.append("---")
    report.append("*Report generated by AeroCore Ads agent*")

    return "\n".join(report)


if __name__ == "__main__":
    report = generate_report()

    # Save to output
    output_path = "/Volumes/T9 Drive 1/SERVER7-AEROCORE/aerocore-lab/instances/aerocore-ads/output/weekly-report.md"
    with open(output_path, "w") as f:
        f.write(report)

    print(report)
    print(f"\nReport saved to: {output_path}")
