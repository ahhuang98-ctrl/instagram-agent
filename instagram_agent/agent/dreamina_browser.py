import asyncio
import json
import os
import time
from pathlib import Path

import requests as _requests

from browser_use import Agent
from browser_use.browser import BrowserProfile, BrowserSession
from browser_use.llm.anthropic.chat import ChatAnthropic

from agent.image_generator import ImageGenerationError
from agent.logger import get_logger

logger = get_logger("dreamina_browser")

DOWNLOADS_DIR = Path(__file__).parent.parent / "downloads"
BROWSER_PROFILE_DIR = Path.home() / ".instagram-agent" / "dreamina-profile"

_CDN_HOST = "ibyteimg.com"
_MIME_TO_EXT = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
_DL_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def _webp_to_jpeg(path: Path) -> Path:
    if path.suffix.lower() != ".webp":
        return path
    try:
        from PIL import Image
        dest = path.with_suffix(".jpg")
        with Image.open(path) as img:
            img.convert("RGB").save(dest, "JPEG", quality=92)
        path.unlink()
        logger.info(f"Converted WebP to JPEG: {dest.name}")
        return dest
    except Exception as e:
        logger.warning(f"WebP conversion failed: {e}")
        return path


def _validate_dimensions(path: Path, min_side: int = 512) -> bool:
    try:
        from PIL import Image
        with Image.open(path) as img:
            w, h = img.size
            return w >= min_side and h >= min_side
    except Exception:
        return False


async def _scrape_cdn_urls(page) -> list[str]:
    """Extract CDN image URLs from DOM, sorted largest-first by natural dimensions."""
    try:
        raw = await page.evaluate(
            f"() => JSON.stringify("
            f"Array.from(document.querySelectorAll('img'))"
            f".filter(img => img.src.includes('{_CDN_HOST}') && img.naturalWidth > 0)"
            f".sort((a, b) => (b.naturalWidth * b.naturalHeight) - (a.naturalWidth * a.naturalHeight))"
            f".map(img => img.src)"
            f")"
        )
        urls = json.loads(raw) if raw else []
        return [u for u in urls if isinstance(u, str) and u.startswith("https://")]
    except Exception as e:
        logger.warning(f"DOM image scrape failed: {e}")
        return []


async def _download_best(urls: list[str]) -> str | None:
    """Try each URL in order, return local path of first image that downloads successfully."""
    for i, url in enumerate(urls[:8]):
        try:
            resp = await asyncio.to_thread(_requests.get, url, headers=_DL_HEADERS, timeout=30)
            if not resp.ok:
                logger.debug(f"HTTP {resp.status_code} for {url[:70]}")
                continue
            mime = resp.headers.get("content-type", "image/jpeg").split(";")[0].strip()
            if not mime.startswith("image/"):
                continue
            ext = _MIME_TO_EXT.get(mime, "jpg")
            out = DOWNLOADS_DIR / f"dreamina_{int(time.time())}_{i}.{ext}"
            out.write_bytes(resp.content)
            out = _webp_to_jpeg(out)
            logger.info(f"Downloaded: {out.name}")
            return str(out)
        except Exception as e:
            logger.debug(f"Download failed for {url[:70]}: {e}")
    return None


async def _generate_image_via_browser(prompt: str) -> str:
    DOWNLOADS_DIR.mkdir(exist_ok=True)
    BROWSER_PROFILE_DIR.mkdir(exist_ok=True)

    email = os.environ["DREAMINA_EMAIL"]
    password = os.environ["DREAMINA_PASSWORD"]

    llm = ChatAnthropic(model="claude-haiku-4-5-20251001")

    task = (
        f"Go to https://dreamina.capcut.com/ai-tool/generate?type=image. "
        f"Wait for the page to load. If you are not logged in, click Sign in and use "
        f"email '{email}' and password '{password}'. "
        f"Once on the image generation page, confirm 'AI Image' mode is selected (not AI Video). "
        f"If AI Video is shown, click the mode selector and choose 'AI Image'. "
        f"Click the prompt text input at the bottom, clear any existing text, then type exactly: {prompt!r}. "
        f"Click the Generate button ONCE — do NOT click Generate again for any reason. "
        f"Wait up to 90 seconds for the new images to fully appear in the grid with no loading spinners. "
        f"Once the generated images are clearly visible, your task is COMPLETE. Do NOT click anything else."
    )

    browser_profile = BrowserProfile(
        headless=False,
        downloads_path=DOWNLOADS_DIR,
        user_data_dir=BROWSER_PROFILE_DIR,
        keep_alive=True,
    )

    session = BrowserSession(browser_profile=browser_profile)
    await session.start()

    agent = Agent(
        task=task,
        llm=llm,
        browser_session=session,
        max_failures=5,
        use_thinking=False,
    )

    logger.info(f"Starting browser agent for prompt: '{prompt[:80]}...'")
    await agent.run()

    # Agent has confirmed images are visible — scrape their CDN URLs from the DOM.
    page = await session.must_get_current_page()
    cdn_urls = await _scrape_cdn_urls(page)

    if cdn_urls:
        logger.info(f"Found {len(cdn_urls)} CDN image URL(s) in DOM — downloading...")
        result = await _download_best(cdn_urls)
        if result:
            return result

    raise ImageGenerationError("No valid image found in page DOM after generation.")


def generate_image_dreamina(prompt: str) -> str:
    try:
        return asyncio.run(_generate_image_via_browser(prompt))
    except ImageGenerationError:
        raise
    except Exception as e:
        raise ImageGenerationError(f"Browser-based Dreamina generation failed: {e}") from e
