import os

import requests

from agent.logger import get_logger
from agent.retry_utils import http_retry

logger = get_logger("instagram")

GRAPH_API_BASE = "https://graph.facebook.com/v25.0"


class InstagramAPIError(Exception):
    def __init__(self, message: str, response_data: dict | None = None):
        super().__init__(message)
        self.response_data = response_data


def _get_credentials() -> tuple[str, str]:
    return os.environ["INSTAGRAM_USER_ID"], os.environ["INSTAGRAM_ACCESS_TOKEN"]


@http_retry(logger)
def _http_post(url: str, data: dict, timeout: int) -> requests.Response:
    resp = requests.post(url, data=data, timeout=timeout)
    if not resp.ok:
        logger.error(f"API error {resp.status_code}: {resp.text[:500]}")
        resp.raise_for_status()
    return resp


def _create_media_container(
    ig_user_id: str,
    access_token: str,
    image_url: str,
    caption: str,
) -> str:
    endpoint = f"{GRAPH_API_BASE}/{ig_user_id}/media"
    payload: dict = {"image_url": image_url, "access_token": access_token, "caption": caption}

    logger.info("Creating Feed media container...")
    try:
        resp = _http_post(endpoint, data=payload, timeout=30)
    except requests.RequestException as e:
        raise InstagramAPIError(f"Container creation request failed: {e}") from e

    result = resp.json()
    if "error" in result:
        raise InstagramAPIError(
            f"Instagram API error: {result['error'].get('message')}",
            response_data=result,
        )
    if "id" not in result:
        raise InstagramAPIError(
            f"Container ID missing from response: {result}", response_data=result
        )

    container_id = result["id"]
    logger.info(f"Feed container created: {container_id}")
    return container_id


def _publish_container(
    ig_user_id: str, access_token: str, creation_id: str
) -> str:
    endpoint = f"{GRAPH_API_BASE}/{ig_user_id}/media_publish"
    payload = {"creation_id": creation_id, "access_token": access_token}

    logger.info(f"Publishing container {creation_id}...")
    try:
        resp = _http_post(endpoint, data=payload, timeout=30)
    except requests.RequestException as e:
        raise InstagramAPIError(f"Publish request failed: {e}") from e

    result = resp.json()
    if "error" in result:
        raise InstagramAPIError(
            f"Instagram publish error: {result['error'].get('message')}",
            response_data=result,
        )

    media_id = result["id"]
    logger.info(f"Published. Media ID: {media_id}")
    return media_id


def post_feed(image_url: str, caption: str) -> str:
    """Post an image to the Instagram feed. Returns the published media ID."""
    ig_user_id, access_token = _get_credentials()
    container_id = _create_media_container(ig_user_id, access_token, image_url, caption)
    return _publish_container(ig_user_id, access_token, container_id)
