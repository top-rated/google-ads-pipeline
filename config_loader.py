import os
from pathlib import Path
import yaml
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent

# Load .env file if it exists
load_dotenv(BASE_DIR / ".env")


def load_config() -> dict:
    """
    Loads configuration from environment variables or config.yaml.
    Environment variables take precedence.
    """
    config_path = BASE_DIR / "config.yaml"
    config = {}

    # 1. Try loading from config.yaml if it exists
    if config_path.exists():
        config = yaml.safe_load(config_path.read_text()) or {}

    # 2. Override with environment variables if present
    env_mapping = {
        "developer_token": "GOOGLE_ADS_DEVELOPER_TOKEN",
        "client_id": "GOOGLE_ADS_CLIENT_ID",
        "client_secret": "GOOGLE_ADS_CLIENT_SECRET",
        "refresh_token": "GOOGLE_ADS_REFRESH_TOKEN",
        "login_customer_id": "GOOGLE_ADS_LOGIN_CUSTOMER_ID",
    }

    for key, env_var in env_mapping.items():
        val = os.getenv(env_var)
        if val:
            config[key] = val

    # Verify required keys
    required_keys = ["developer_token", "client_id", "client_secret", "refresh_token", "login_customer_id"]
    missing = [k for k in required_keys if k not in config]
    if missing:
        raise ValueError(
            f"Missing required configuration: {', '.join(missing)}. "
            "Set them as environment variables or in config.yaml."
        )

    return config


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
