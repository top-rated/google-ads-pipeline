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
    If campaigns.yaml is missing or the list is empty, returns an empty set.
    """
    campaigns_path = BASE_DIR / "campaigns.yaml"
    if not campaigns_path.exists():
        return set()
    data = yaml.safe_load(campaigns_path.read_text()) or {}
    names = data.get("campaigns") or []
    return set(names)


def save_campaigns(names: set):
    """
    Saves the set of campaign names to campaigns.yaml.
    """
    campaigns_path = BASE_DIR / "campaigns.yaml"
    data = {"campaigns": sorted(list(names))}
    campaigns_path.write_text(yaml.dump(data, sort_keys=False))


    return GoogleAdsClient.load_from_dict(credentials)


def get_all_campaign_names(client, customer_id: str) -> list:
    """
    Fetch all ENABLED campaign names from the Google Ads account.
    Useful for 'exploring' what campaigns can be added to the pipeline.
    """
    ga_svc = client.get_service("GoogleAdsService")
    query = """
        SELECT campaign.name
        FROM campaign
        WHERE campaign.status = 'ENABLED'
    """
    response = ga_svc.search(customer_id=customer_id, query=query)
    return [row.campaign.name for row in response]


def filter_campaigns(rows, campaign_name_getter, allowed: set):
    """
    Filter a list of API result rows to only our campaigns.
    In SaaS mode, if allowed is empty, NO rows pass through (Opt-In).
    """
    if not allowed:
        return []
    return [r for r in rows if campaign_name_getter(r) in allowed]
