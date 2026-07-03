"""Facebook Graph API posting helper."""

import requests

import config

GRAPH_BASE = f"https://graph.facebook.com/{config.FACEBOOK_GRAPH_VERSION}"


def _page_target() -> tuple[str, str]:
    if not config.FACEBOOK_PAGE_ID:
        raise RuntimeError("FACEBOOK_PAGE_ID is not set")
    if not config.FACEBOOK_PAGE_ACCESS_TOKEN:
        raise RuntimeError("FACEBOOK_PAGE_ACCESS_TOKEN is not set")
    return config.FACEBOOK_PAGE_ID, config.FACEBOOK_PAGE_ACCESS_TOKEN


def _group_target() -> tuple[str, str]:
    if not config.FACEBOOK_GROUP_ID:
        raise RuntimeError("FACEBOOK_GROUP_ID is not set")
    if not config.FACEBOOK_ACCESS_TOKEN:
        raise RuntimeError("FACEBOOK_ACCESS_TOKEN is not set")
    return config.FACEBOOK_GROUP_ID, config.FACEBOOK_ACCESS_TOKEN


def send_post(message: str, link: str = None) -> str:
    """Post text to the configured Facebook Page or Group feed."""
    target_id, token = _group_target() if config.FACEBOOK_TARGET == "group" else _page_target()
    payload = {"message": message, "access_token": token}
    if link:
        payload["link"] = link

    resp = requests.post(f"{GRAPH_BASE}/{target_id}/feed", data=payload, timeout=20)
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"Facebook API error: {data}")
    return data.get("id", "")
