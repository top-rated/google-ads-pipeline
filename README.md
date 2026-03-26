# Google Ads Python Pipeline

Minimal Python scripts for managing Google Ads Search campaigns via the API.
Useful when you run campaigns from an MCC or a shared account and need
read-only monitoring plus conservative automated optimization.

## Professional Deployment (Recommended)

For a stable, production-ready setup on a VPS, use Docker. This ensures all dependencies are correctly installed and scripts run on a reliable schedule.

See the [VPS Deployment Guide](deploy_vps.md) for step-by-step instructions.

### Quick Start (Docker)
1. `cp .env.example .env` (fill in your keys)
2. `docker compose up -d`

## Local Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Get Google Ads API credentials
...

You need:
- A [Google Ads developer token](https://developers.google.com/google-ads/api/docs/get-started/dev-token)
- OAuth2 credentials (client ID + secret + refresh token)
  — follow the [OAuth2 setup guide](https://developers.google.com/google-ads/api/docs/oauth/cloud-project)

### 3. Create config.yaml

```bash
cp config.yaml.example config.yaml
```

Edit `config.yaml` and fill in your credentials and thresholds.

### 4. (Optional) Create campaigns.yaml

```bash
cp campaigns.yaml.example campaigns.yaml
```

List only the campaign names you want to manage.
If you skip this step or leave the list empty, all campaigns in the account are included.

### 5. Run

```bash
# Daily monitor
python3 monitor.py
python3 monitor.py --days 7

# Weekly optimizer (dry run first)
python3 optimize.py --dry-run
python3 optimize.py
```

## Cron example

```cron
# Monitor every morning at 08:00
0 8 * * * cd /path/to/google-ads-pipeline && python3 monitor.py >> logs/monitor.log 2>&1

# Optimize every Monday at 09:00
0 9 * * 1 cd /path/to/google-ads-pipeline && python3 optimize.py >> logs/optimize.log 2>&1
```

## Optimization rules

The optimizer applies these rules in order, stopping at `max_changes_per_run`:

1. **Pause wasteful keywords** — spend ≥ `wasteful_spend_threshold` and 0 conversions
2. **Add negative keywords** — search terms with ≥ `min_clicks_for_negative` clicks, 0 conversions, CTR < 2%
3. **Check TARGET_CPA readiness** — prints a recommendation if the configured campaign
   has ≥ `min_conversions_for_cpa` conversions in the last 30 days

All changes are guarded by `min_days_before_optimize` — the optimizer does nothing during
the Smart Bidding learning phase (typically first 14 days after launch).

All changes are logged as JSON to the `logs/` directory.

## API version

Tested with `google-ads` library v23.x (Google Ads API v23).

Notable v23 patterns used:
- `c._pb.maximize_conversions.SetInParent()` for proto-plus oneof fields
- `explicitly_shared = False` required for MAXIMIZE_CONVERSIONS budgets
- `contains_eu_political_advertising` must be set as an enum, not a bool

## License

MIT
