#!/usr/bin/env python3
"""
Weekly optimization script for Google Ads campaigns.
WRITES CHANGES — use with care.

Usage:
  python3 optimize.py --dry-run     # preview changes only
  python3 optimize.py               # apply changes

Reads credentials and thresholds from config.yaml.
Filters to campaigns listed in campaigns.yaml (if present).

Rules applied:
  1. Pause keywords with spend >= wasteful_spend_threshold and 0 conversions
  2. Add campaign-level negative keywords from search terms with
     >= min_clicks_for_negative clicks, 0 conversions, CTR < 2%
  3. Check if a campaign is ready for TARGET_CPA bidding
  4. No changes during first min_days_before_optimize days (Smart Bidding warmup)
  5. Max max_changes_per_run changes per run
  6. All changes logged to logs/ directory
"""

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

from config_loader import load_config, load_campaigns, connect

LOG_DIR = Path(__file__).parent / "logs"


def days_since_launch(launch_date: str) -> int:
    launch = datetime.strptime(launch_date, "%Y-%m-%d")
    return (datetime.now() - launch).days


def find_wasteful_keywords(client, customer_id: str, allowed_campaigns: set,
                            spend_threshold: float, days: int):
    """Keywords with spend >= threshold and 0 conversions."""
    ga_svc = client.get_service("GoogleAdsService")
    date_from = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    date_to = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    threshold_micros = int(spend_threshold * 1_000_000)

    query = f"""
        SELECT campaign.name, ad_group.name, ad_group.id,
               ad_group_criterion.criterion_id,
               ad_group_criterion.keyword.text, ad_group_criterion.keyword.match_type,
               ad_group_criterion.status,
               metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions
        FROM keyword_view
        WHERE campaign.status != 'REMOVED'
          AND ad_group_criterion.status = 'ENABLED'
          AND segments.date BETWEEN '{date_from}' AND '{date_to}'
          AND metrics.cost_micros > {threshold_micros}
          AND metrics.conversions = 0
        ORDER BY metrics.cost_micros DESC
    """
    response = ga_svc.search(customer_id=customer_id, query=query)
    return [
        {
            "campaign": r.campaign.name,
            "ad_group": r.ad_group.name,
            "ag_id": r.ad_group.id,
            "crit_id": r.ad_group_criterion.criterion_id,
            "keyword": r.ad_group_criterion.keyword.text,
            "match": r.ad_group_criterion.keyword.match_type.name,
            "cost": r.metrics.cost_micros / 1_000_000,
            "clicks": r.metrics.clicks,
            "impressions": r.metrics.impressions,
        }
        for r in response
        if not allowed_campaigns or r.campaign.name in allowed_campaigns
    ]


def find_negative_keyword_candidates(client, customer_id: str, allowed_campaigns: set,
                                      min_clicks: int, days: int):
    """Search terms with >= min_clicks, 0 conversions, CTR < 2%."""
    ga_svc = client.get_service("GoogleAdsService")
    date_from = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    date_to = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    query = f"""
        SELECT campaign.name, campaign.id,
               search_term_view.search_term,
               metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions
        FROM search_term_view
        WHERE campaign.status != 'REMOVED'
          AND segments.date BETWEEN '{date_from}' AND '{date_to}'
          AND metrics.clicks > {min_clicks}
          AND metrics.conversions = 0
        ORDER BY metrics.cost_micros DESC
        LIMIT 20
    """
    response = ga_svc.search(customer_id=customer_id, query=query)
    candidates = []
    for r in response:
        if allowed_campaigns and r.campaign.name not in allowed_campaigns:
            continue
        ctr = r.metrics.clicks / r.metrics.impressions if r.metrics.impressions > 0 else 0
        if ctr < 0.02:
            candidates.append({
                "campaign": r.campaign.name,
                "campaign_id": r.campaign.id,
                "term": r.search_term_view.search_term,
                "clicks": r.metrics.clicks,
                "cost": r.metrics.cost_micros / 1_000_000,
                "ctr": ctr,
            })
    return candidates


def pause_keyword(client, customer_id: str, ag_id: int, crit_id: int, dry_run: bool):
    if dry_run:
        return
    ag_crit_svc = client.get_service("AdGroupCriterionService")
    op = client.get_type("AdGroupCriterionOperation")
    c = op.update
    c.resource_name = f"customers/{customer_id}/adGroupCriteria/{ag_id}~{crit_id}"
    c.status = client.enums.AdGroupCriterionStatusEnum.PAUSED
    op.update_mask.paths.append("status")
    ag_crit_svc.mutate_ad_group_criteria(customer_id=customer_id, operations=[op])


def add_negative_keyword(client, customer_id: str, campaign_id: int, term: str, dry_run: bool):
    if dry_run:
        return
    crit_svc = client.get_service("CampaignCriterionService")
    op = client.get_type("CampaignCriterionOperation")
    cc = op.create
    cc.campaign = f"customers/{customer_id}/campaigns/{campaign_id}"
    cc.negative = True
    cc.keyword.text = term
    cc.keyword.match_type = client.enums.KeywordMatchTypeEnum.EXACT
    crit_svc.mutate_campaign_criteria(customer_id=customer_id, operations=[op])


def check_target_cpa_readiness(client, customer_id: str, config: dict):
    """Check if the designated campaign is ready to switch to TARGET_CPA."""
    campaign_name = config.get("target_cpa_campaign", "").strip()
    if not campaign_name:
        return None

    min_conv = config.get("min_conversions_for_cpa", 30)
    target_cpa = config.get("target_cpa", 0)

    ga_svc = client.get_service("GoogleAdsService")
    date_from = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    date_to = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    query = f"""
        SELECT campaign.name, metrics.conversions
        FROM campaign
        WHERE campaign.name = '{campaign_name}'
          AND segments.date BETWEEN '{date_from}' AND '{date_to}'
    """
    response = ga_svc.search(customer_id=customer_id, query=query)
    for row in response:
        conv = row.metrics.conversions
        if conv >= min_conv:
            return f"{campaign_name}: {conv:.0f} conversions → READY for TARGET_CPA {target_cpa}"
        else:
            return f"{campaign_name}: {conv:.0f}/{min_conv} conversions needed for TARGET_CPA"
    return f"{campaign_name}: no data in last 30 days"


def main():
    parser = argparse.ArgumentParser(description="Google Ads weekly optimizer")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without applying")
    parser.add_argument("--days", type=int, default=14, help="Lookback period (default: 14)")
    args = parser.parse_args()

    config = load_config()
    allowed = load_campaigns()
    customer_id = str(config["customer_id"])
    client = connect(config)

    max_changes = config.get("max_changes_per_run", 5)
    spend_threshold = config.get("wasteful_spend_threshold", 50.0)
    min_clicks = config.get("min_clicks_for_negative", 3)
    min_days = config.get("min_days_before_optimize", 14)
    launch_date = config.get("launch_date", "")

    days_live = days_since_launch(launch_date) if launch_date else 999

    LOG_DIR.mkdir(exist_ok=True)
    mode = "DRY RUN" if args.dry_run else "LIVE"

    print("=" * 70)
    print(f"GOOGLE ADS OPTIMIZER — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"Account: {customer_id} | Mode: {mode} | Days since launch: {days_live} | Lookback: {args.days}d")
    print("=" * 70)

    changes = []

    # Guard: don't optimize too early
    if days_live < min_days:
        print(f"\n⚠ Campaigns only {days_live} days old. Need {min_days}+ days for Smart Bidding to learn.")
        print("  Skipping all changes. Run monitor.py instead.")
        return

    # 1. Wasteful keywords
    print(f"\n## WASTEFUL KEYWORDS (>{spend_threshold} spend, 0 conversions)")
    wasteful = find_wasteful_keywords(client, customer_id, allowed, spend_threshold, args.days)
    if wasteful:
        for kw in wasteful:
            if len(changes) >= max_changes:
                print(f"  ... skipping rest (max {max_changes} changes per run)")
                break
            action = (
                f"PAUSE keyword '{kw['keyword']}' ({kw['match']}) "
                f"in {kw['campaign']}/{kw['ad_group']} — "
                f"{kw['cost']:.2f} spent, {kw['clicks']} clicks, 0 conv"
            )
            print(f"  {'[DRY] ' if args.dry_run else ''}{action}")
            pause_keyword(client, customer_id, kw["ag_id"], kw["crit_id"], args.dry_run)
            changes.append({"action": "pause_keyword", "detail": action, "applied": not args.dry_run})
    else:
        print("  None found")

    # 2. Negative keyword candidates
    print(f"\n## NEGATIVE KEYWORD CANDIDATES (>{min_clicks} clicks, 0 conv, CTR <2%)")
    neg_candidates = find_negative_keyword_candidates(client, customer_id, allowed, min_clicks, args.days)
    if neg_candidates:
        for nc in neg_candidates:
            if len(changes) >= max_changes:
                print(f"  ... skipping rest (max {max_changes} changes per run)")
                break
            action = (
                f"ADD negative '{nc['term']}' to {nc['campaign']} — "
                f"{nc['clicks']} clicks, {nc['cost']:.2f}, CTR {nc['ctr']:.1%}"
            )
            print(f"  {'[DRY] ' if args.dry_run else ''}{action}")
            add_negative_keyword(client, customer_id, nc["campaign_id"], nc["term"], args.dry_run)
            changes.append({"action": "add_negative", "detail": action, "applied": not args.dry_run})
    else:
        print("  None found")

    # 3. TARGET_CPA readiness check
    print("\n## BIDDING STRATEGY CHECK")
    cpa_status = check_target_cpa_readiness(client, customer_id, config)
    if cpa_status:
        print(f"  {cpa_status}")
        if "READY" in cpa_status:
            changes.append({"action": "recommendation", "detail": cpa_status})
    else:
        print("  target_cpa_campaign not configured in config.yaml — skipping")

    # Log changes
    log_file = LOG_DIR / f"optimize_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    log_data = {
        "timestamp": datetime.now().isoformat(),
        "mode": mode,
        "days_since_launch": days_live,
        "lookback_days": args.days,
        "changes": changes,
    }
    log_file.write_text(json.dumps(log_data, indent=2, ensure_ascii=False))

    print(f"\n## SUMMARY")
    print(f"  Changes {'proposed' if args.dry_run else 'applied'}: {len(changes)}")
    print(f"  Log: {log_file}")
    print("=" * 70)


if __name__ == "__main__":
    main()
