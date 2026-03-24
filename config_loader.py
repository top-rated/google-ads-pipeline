"""
Shared config loader for all pipeline scripts.
Reads config.yaml and campaigns.yaml from the same directory as this file.
"""

from pathlib import Path
import yaml

BASE_DIR = Path(__file__).parent


def load_config() -> dict:
    config_path = BASE_DIR / "config.yaml"
    if not config_path.exists():
        raise FileNotFoundError(
            "config.yaml not found. Copy config.yaml.example to config.yaml and fill in your values."
        )
    return yaml.safe_load(config_path.read_text())


def load_campaigns() -> set:
    """
    Returns the set of campaign names to manage.
    If campaigns.yaml is missing or the list is empty, returns an empty set
    which means 'include all campaigns in the account'.
    """
    campaigns_path = BASE_DIR / "campaigns.yaml"
    if not campaigns_path.exists():
        return set()
    data = yaml.safe_load(campaigns_path.read_text()) or {}
    names = data.get("campaigns") or []
    return set(names)


def connect(config: dict):
    """Return a GoogleAdsClient loaded from config dict."""
    from google.ads.googleads.client import GoogleAdsClient

    credentials = {
        "developer_token": config["developer_token"],
        "client_id": config["client_id"],
        "client_secret": config["client_secret"],
        "refresh_token": config["refresh_token"],
        "login_customer_id": str(config["login_customer_id"]),
        "use_proto_plus": True,
    }
    return GoogleAdsClient.load_from_dict(credentials)


def filter_campaigns(rows, campaign_name_getter, allowed: set):
    """
    Filter a list of API result rows to only our campaigns.
    If allowed is empty, all rows pass through.
    """
    if not allowed:
        return list(rows)
    return [r for r in rows if campaign_name_getter(r) in allowed]
