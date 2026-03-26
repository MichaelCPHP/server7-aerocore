# Post-Launch Monitoring Plan

**Created:** 2026-03-23
**Campaigns Live Since:** 2026-03-23
**First Review Target:** 2026-03-26 (3 days of data)
**Full Review Target:** 2026-03-30 (1 week of data)

---

## Active Campaigns

| Campaign | Daily Budget | Bidding | Max CPC | Ad Groups |
|----------|-------------|---------|---------|-----------|
| CarbideRecovery_2026Q2 | $55 | Maximize Clicks | $10 | Scrap Carbide Buying ($5), Tungsten Scrap Buying ($5) |
| AerospaceAlloys_2026Q2 | $40 | Maximize Clicks | $10 | Inconel & Titanium ($5), Tool Steel & HSS ($5) |
| GeneralScrap_2026Q2 | $26 | Maximize Clicks | $10 | General Manufacturing Scrap ($5) |
| CallOnly_ScrapBuying_2026Q2 | $12 | Maximize Clicks | $8 | Scrap Carbide & Alloy Calls ($6) |
| **Total** | **$133/day ($3,990/mo)** | | | **6 ad groups** |

All campaigns: TARGET_SPEND strategy, SoCal geo targeting (8 counties), Mon-Fri 7am-6pm PT scheduling, UTM tracking enabled.

---

## 3-Day Check (Target: 2026-03-26)

- [ ] Pull impression and click data per campaign
- [ ] Verify ads are approved and serving (check for any disapprovals)
- [ ] Confirm conversion tracking is recording events
- [ ] Check if financial services certification notification is blocking anything
- [ ] Review initial search term report for irrelevant queries

## 1-Week Check (Target: 2026-03-30)

- [ ] **Search Term Report** — identify new negative keywords and keyword opportunities
- [ ] **Quality Score Check** — review keyword Quality Scores and landing page experience ratings
- [ ] **Impression Share** — `metrics.search_impression_share` (what % of eligible impressions we're getting)
- [ ] **Top Position Rate** — `metrics.search_top_impression_percentage` and `metrics.search_absolute_top_impression_percentage`
- [ ] **Average CPC** — what we're actually paying vs. max CPC ceilings
- [ ] **CTR by Ad Group** — identify underperformers
- [ ] **Conversion Tracking Verification** — confirm real conversions are recording (not just clicks)
- [ ] **Budget Utilization** — are campaigns spending their full daily budget or underspending?

## 2-Week Check (Target: 2026-04-06)

- [ ] **A/B Test Results** — compare Variant A vs Variant B CTR and conversion rates across Carbide, Tungsten, and Call ad groups
- [ ] **Pause losing ad variants** if clear winner emerges
- [ ] **Keyword Performance** — pause keywords with high spend but zero conversions
- [ ] **Bid Adjustments** — increase bids on high-converting keywords, lower on underperformers
- [ ] **Geographic Performance** — check which SoCal counties are converting best
- [ ] **Device Performance** — mobile vs desktop split
- [ ] **Ad Schedule Performance** — any time-of-day patterns?

## Ongoing (Monthly)

- [ ] Weekly performance report (script: `scripts/weekly-performance-report.py`)
- [ ] Search term report review and negative keyword updates
- [ ] Budget reallocation based on campaign ROI
- [ ] Consider Performance Max (Task 4.3) — only after 30+ conversions from Search
- [ ] Consider bidding strategy switch to Target CPA after 30+ conversions

---

## Key Metrics to Query (Google Ads API)

```sql
-- Impression share and position metrics
SELECT campaign.name, metrics.impressions, metrics.clicks, metrics.ctr,
       metrics.average_cpc, metrics.cost_micros,
       metrics.search_impression_share,
       metrics.search_top_impression_percentage,
       metrics.search_absolute_top_impression_percentage
FROM campaign
WHERE campaign.status = 'ENABLED'
AND segments.date DURING LAST_7_DAYS

-- Search terms triggering ads
SELECT search_term_view.search_term, campaign.name, ad_group.name,
       metrics.impressions, metrics.clicks, metrics.cost_micros
FROM search_term_view
WHERE campaign.status = 'ENABLED'
AND segments.date DURING LAST_7_DAYS
ORDER BY metrics.impressions DESC

-- Quality Scores
SELECT ad_group_criterion.keyword.text, ad_group_criterion.quality_info.quality_score,
       ad_group_criterion.quality_info.creative_relevance_status,
       ad_group_criterion.quality_info.search_predicted_ctr,
       ad_group_criterion.quality_info.post_click_quality_score
FROM keyword_view
WHERE campaign.status = 'ENABLED'
```

---

## Notes

- All campaigns use the same bidding type (Maximize Clicks / TARGET_SPEND) but each has independent budgets and CPC ceilings
- Extensions shared across all 4 campaigns: 4 sitelinks, 9 callouts, 2 structured snippets, call extension
- A/B test active in 3 ad groups (Carbide, Tungsten, Call) — 2 ads per group
- Aerospace and General Scrap ad groups have 1 ad each (no A/B yet)
