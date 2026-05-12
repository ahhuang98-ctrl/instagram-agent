import os

import requests

from agent.logger import get_logger

logger = get_logger("image_host")

IMGBB_UPLOAD_URL = "https://api.imgbb.com/1/upload"


class ImageHostingError(Exception):
    pass


def upload_image_url_to_imgbb(
    image_url: str,
    expiration: int = 0,
    name: str | None = None,
) -> str:
    """
    Upload an image (by URL) to imgbb and return the permanent public URL.

    imgbb fetches the image from the source URL server-side, so no local
    download is needed. fal.ai temporary URLs expire; this gives Instagram
    a stable URL to fetch from.
    """
    api_key = os.environ["IMGBB_API_KEY"]

    payload: dict = {"key": api_key, "image": image_url}
    if expiration:
        payload["expiration"] = expiration
    if name:
        payload["name"] = name

    logger.info(f"Uploading to imgbb from: {image_url[:80]}...")
    try:
        response = requests.post(IMGBB_UPLOAD_URL, data=payload, timeout=60)
        response.raise_for_status()
    except requests.RequestException as e:
        raise ImageHostingError(f"imgbb upload request failed: {e}") from e

    data = response.json()
    if not data.get("success"):
        raise ImageHostingError(
            f"imgbb reported failure. Status {data.get('status')}: {data}"
        )

    public_url = data["data"]["url"]
    logger.info(f"Image hosted at: {public_url}")
    return public_url
