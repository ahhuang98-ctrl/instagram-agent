import base64
import io
import os

import requests
from PIL import Image

from agent.logger import get_logger
from agent.retry_utils import http_retry

logger = get_logger("image_host")

IMGBB_UPLOAD_URL = "https://api.imgbb.com/1/upload"


class ImageHostingError(Exception):
    pass


@http_retry(logger)
def _http_post(url: str, data: dict, timeout: int) -> requests.Response:
    resp = requests.post(url, data=data, timeout=timeout)
    resp.raise_for_status()
    return resp


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
        response = _http_post(IMGBB_UPLOAD_URL, data=payload, timeout=60)
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


def _to_jpeg_bytes(file_path: str) -> bytes:
    """Return JPEG bytes for any image file, converting from WebP/PNG if needed."""
    with Image.open(file_path) as img:
        if img.format == "JPEG":
            with open(file_path, "rb") as f:
                return f.read()
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="JPEG", quality=95)
        return buf.getvalue()


def upload_local_image_to_imgbb(
    file_path: str,
    expiration: int = 0,
    name: str | None = None,
) -> str:
    """Upload a local image file to imgbb via base64 encoding and return the permanent public URL."""
    api_key = os.environ["IMGBB_API_KEY"]

    image_bytes = _to_jpeg_bytes(file_path)
    encoded = base64.b64encode(image_bytes).decode("utf-8")

    payload: dict = {"key": api_key, "image": encoded}
    if expiration:
        payload["expiration"] = expiration
    if name:
        payload["name"] = name

    logger.info(f"Uploading local image to imgbb: {file_path}")
    try:
        response = _http_post(IMGBB_UPLOAD_URL, data=payload, timeout=60)
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
