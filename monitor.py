#!/usr/bin/env python3
"""
Daily monitoring script for Google Ads campaigns.
Read-only — no changes made. Outputs report to stdout.

Usage:
  python3 monitor.py
  python3 monitor.py --days 7

Reads credentials and settings from config.yaml.
Filters to campaigns listed in campaigns.yaml (if present).
"""

import argparse
from datetime import datetime, timedelta

from config_loader import load_config, load_campaigns, connect


def check_ad_approval(client, customer_id: str, allowed_campaigns: set):
    """Check approval status of all ads."""
    ga_svc = client.get_service("GoogleAdsService")
    query = """
        SELECT campaign.name, ad_group.name, ad_group_ad.ad.id,
               ad_group_ad.policy_summary.approval_status,
               ad_group_ad.policy_summary.policy_topic_entries
        FROM ad_group_ad
        WHERE campaign.status != 'REMOVED'
        ORDER BY campaign.name
    """
    response = ga_svc.search(customer_id=customer_id, query=query)

    issues = []
    total = 0
    approved = 0
    for row in response:
        if allowed_campaigns and row.campaign.name not in allowed_campaigns:
            continue
        total += 1
        status = row.ad_group_ad.policy_summary.approval_status.name
        if status in ("APPROVED", "APPROVED_LIMITED"):
            approved += 1
        else:
            topics = [e.topic for e in row.ad_group_ad.policy_summary.policy_topic_entries]
            issues.append({
                "campaign": row.campaign.name,
                "ad_group": row.ad_group.name,
                "ad_id": row.ad_group_ad.ad.id,
                "status": status,
                "topics": topics,
            })
    return total, approved, issues


def get_performance(client, customer_id: str, allowed_campaigns: set, days: int = 1):
    """Get campaign performance metrics."""
    ga_svc = client.get_service("GoogleAdsService")
    date_from = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    date_to = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    query = f"""
        SELECT campaign.name, campaign.status,
               metrics.impressions, metrics.clicks, metrics.ctr,
               metrics.cost_micros, metrics.conversions, metrics.cost_per_conversion,
               metrics.average_cpc
        FROM campaign
        WHERE campaign.status != 'REMOVED'
          AND segments.date BETWEEN '{date_from}' AND '{date_to}'
        ORDER BY metrics.cost_micros DESC
    """
    response = ga_svc.search(customer_id=customer_id, query=query)
    results = []
    for row in response:
        if allowed_campaigns and row.campaign.name not in allowed_campaigns:
            continue
        results.append({
            "name": row.campaign.name,
            "status": row.campaign.status.name,
            "impressions": row.metrics.impressions,
            "clicks": row.metrics.clicks,
            "ctr": row.metrics.ctr,
            "cost": row.metrics.cost_micros / 1_000_000,
            "conversions": row.metrics.conversions,
            "cpc": row.metrics.average_cpc / 1_000_000 if row.metrics.average_cpc else 0,
            "cost_per_conv": row.metrics.cost_per_conversion / 1_000_000 if row.metrics.cost_per_conversion else 0,
        })
    return results, date_from, date_to


def get_keyword_performance(client, customer_id: str, allowed_campaigns: set, days: int = 7):
    """Get keyword-level performance for optimization insights."""
    ga_svc = client.get_service("GoogleAdsService")
    date_from = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    date_to = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    query = f"""
        SELECT campaign.name, ad_group.name,
               ad_group_criterion.keyword.text, ad_group_criterion.keyword.match_type,
               metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions
        FROM keyword_view
        WHERE campaign.status != 'REMOVED'
          AND segments.date BETWEEN '{date_from}' AND '{date_to}'
          AND metrics.impressions > 0
        ORDER BY metrics.cost_micros DESC
        LIMIT 50
    """
    response = ga_svc.search(customer_id=customer_id, query=query)
    results = []
    for row in response:
        if allowed_campaigns and row.campaign.name not in allowed_campaigns:
            continue
        results.append({
            "campaign": row.campaign.name,
            "ad_group": row.ad_group.name,
            "keyword": row.ad_group_criterion.keyword.text,
            "match": row.ad_group_criterion.keyword.match_type.name,
            "impressions": row.metrics.impressions,
            "clicks": row.metrics.clicks,
            "cost": row.metrics.cost_micros / 1_000_000,
            "conversions": row.metrics.conversions,
        })
    return results


def get_search_terms(client, customer_id: str, allowed_campaigns: set, days: int = 7):
    """Get search terms report for negative keyword opportunities."""
    ga_svc = client.get_service("GoogleAdsService")
    date_from = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    date_to = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    query = f"""
        SELECT campaign.name, search_term_view.search_term,
               metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions
        FROM search_term_view
        WHERE campaign.status != 'REMOVED'
          AND segments.date BETWEEN '{date_from}' AND '{date_to}'
          AND metrics.impressions > 0
        ORDER BY metrics.cost_micros DESC
        LIMIT 50
    """
    response = ga_svc.search(customer_id=customer_id, query=query)
    results = []
    for row in response:
        if allowed_campaigns and row.campaign.name not in allowed_campaigns:
            continue
        results.append({
            "campaign": row.campaign.name,
            "term": row.search_term_view.search_term,
            "impressions": row.metrics.impressions,
            "clicks": row.metrics.clicks,
            "cost": row.metrics.cost_micros / 1_000_000,
            "conversions": row.metrics.conversions,
        })
    return results


def run_monitor_report(days: int = 1) -> dict:
    """
    Executes the monitor logic and returns a structured data dictionary.
    Useful for both CLI and API.
    """
    config = load_config()
    allowed = load_campaigns()
    customer_id = str(config["customer_id"])
    client = connect(config)

    report = {
        "timestamp": datetime.now().isoformat(),
        "account_id": customer_id,
        "period_days": days,
        "ad_approvals": {},
        "campaign_performance": {},
        "top_keywords": [],
        "top_search_terms": [],
        "anomalies": []
    }

    # 1. Ad approval status
    total, approved, issues = check_ad_approval(client, customer_id, allowed)
    report["ad_approvals"] = {
        "total": total,
        "approved": approved,
        "issues": issues
    }

    # 2. Campaign performance
    perf, date_from, date_to = get_performance(client, customer_id, allowed, days)
    report["campaign_performance"] = {
        "date_from": date_from,
        "date_to": date_to,
        "data": perf
    }

    # 3. Top keywords (multi-day only)
    if days >= 3:
        report["top_keywords"] = get_keyword_performance(client, customer_id, allowed, days)

    # 4. Search terms (multi-day only)
    if days >= 3:
        report["top_search_terms"] = get_search_terms(client, customer_id, allowed, days)

    # 5. Anomaly detection
    target_cpa = config.get("target_cpa", 0)
    anomalies = []
    for p in perf:
        if p["impressions"] == 0 and p["status"] == "ENABLED":
            anomalies.append(f"⚠ {p['name']}: 0 impressions but ENABLED")
        if p["clicks"] > 10 and p["ctr"] < 0.01:
            anomalies.append(f"⚠ {p['name']}: CTR below 1% ({p['ctr']:.1%})")
        if target_cpa and p["cost_per_conv"] > target_cpa * 2 and p["conversions"] > 0:
            anomalies.append(f"⚠ {p['name']}: CPA is {p['cost_per_conv']:.0f} (target: <{target_cpa})")
    report["anomalies"] = anomalies

    return report


def main():
    parser = argparse.ArgumentParser(description="Google Ads daily monitor (read-only)")
    parser.add_argument("--days", type=int, default=1, help="Number of days to look back (default: 1)")
    args = parser.parse_args()

    report = run_monitor_report(args.days)

    print("=" * 70)
    print(f"GOOGLE ADS MONITOR — {report['timestamp']}")
    print(f"Account: {report['account_id']} | Period: last {report['period_days']} day(s)")
    print("=" * 70)

    # 1. Ad approval status
    print("\n## AD APPROVAL STATUS")
    approvals = report["ad_approvals"]
    print(f"  {approvals['approved']}/{approvals['total']} ads approved")
    if approvals["issues"]:
        print("  ISSUES:")
        for i in approvals["issues"]:
            print(f"    ✗ {i['campaign']} → {i['ad_group']} (ad {i['ad_id']}): {i['status']}")
            if i["topics"]:
                print(f"      Topics: {', '.join(i['topics'])}")

    # 2. Campaign performance
    print("\n## CAMPAIGN PERFORMANCE")
    perf_data = report["campaign_performance"]["data"]
    if perf_data:
        print(f"  {'Campaign':<35} {'Impr':>7} {'Clicks':>7} {'CTR':>7} {'Cost':>9} {'Conv':>6} {'CPC':>7} {'CPA':>9}")
        print("  " + "-" * 97)
        total_cost = 0
        total_conv = 0
        for p in perf_data:
            total_cost += p["cost"]
            total_conv += p["conversions"]
            print(
                f"  {p['name']:<35} {p['impressions']:>7} {p['clicks']:>7} {p['ctr']:>6.1%}"
                f" {p['cost']:>8.2f} {p['conversions']:>6.1f} {p['cpc']:>6.2f} {p['cost_per_conv']:>8.2f}"
            )
        print("  " + "-" * 97)
        print(f"  {'TOTAL':<35} {'':>7} {'':>7} {'':>7} {total_cost:>8.2f} {total_conv:>6.1f}")
    else:
        print("  No data yet (campaigns may still be in review)")

    # 3. Top keywords
    if report["top_keywords"]:
        print("\n## TOP KEYWORDS (by spend)")
        for k in report["top_keywords"][:20]:
            ctr = k["clicks"] / k["impressions"] * 100 if k["impressions"] > 0 else 0
            print(
                f"  {k['campaign'][:25]:<25} {k['keyword']:<35}"
                f" {k['impressions']:>5} imp  {k['clicks']:>3} cl  {ctr:>5.1f}%"
                f"  {k['cost']:>.2f}  {k['conversions']:.0f} conv"
            )

    # 4. Search terms
    if report["top_search_terms"]:
        print("\n## TOP SEARCH TERMS (by spend)")
        for t in report["top_search_terms"][:20]:
            ctr = t["clicks"] / t["impressions"] * 100 if t["impressions"] > 0 else 0
            flag = " ⚠ NO CONV" if t["clicks"] >= 3 and t["conversions"] == 0 else ""
            print(
                f"  {t['campaign'][:25]:<25} {t['term']:<40}"
                f" {t['clicks']:>3} cl  {t['cost']:>.2f}{flag}"
            )

    # 5. Anomaly detection
    print("\n## ANOMALIES")
    if report["anomalies"]:
        for a in report["anomalies"]:
            print(f"  {a}")
    else:
        print("  None detected")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
