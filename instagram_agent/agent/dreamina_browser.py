import asyncio
import os
from pathlib import Path

from browser_use import Agent
from browser_use.browser import BrowserProfile
from browser_use.llm.anthropic.chat import ChatAnthropic

from agent.image_generator import ImageGenerationError
from agent.logger import get_logger

logger = get_logger("dreamina_browser")

DOWNLOADS_DIR = Path(__file__).parent.parent / "downloads"
BROWSER_PROFILE_DIR = Path.home() / ".instagram-agent" / "dreamina-profile"

_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


async def _generate_image_via_browser(prompt: str) -> str:
    DOWNLOADS_DIR.mkdir(exist_ok=True)
    BROWSER_PROFILE_DIR.mkdir(exist_ok=True)

    # Snapshot existing files so we can detect what the agent actually downloads.
    existing_files = set(DOWNLOADS_DIR.iterdir())

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
        f"Click the Generate button and wait up to 90 seconds for the images to appear in the grid. "
        f"Once the generated images are fully visible, scroll to the bottom of the prompt input area "
        f"to ensure the latest generated image is in view. "
        f"Hover over the FIRST (most recent) image in the grid to reveal the download icon, "
        f"then click that download icon to save the image."
    )

    logger.info(f"Starting browser agent for prompt: '{prompt[:80]}...'")

    browser_profile = BrowserProfile(
        headless=False,
        downloads_path=DOWNLOADS_DIR,
        user_data_dir=BROWSER_PROFILE_DIR,
    )
    agent = Agent(
        task=task,
        llm=llm,
        browser_profile=browser_profile,
        max_failures=5,
        use_thinking=False,
    )
    await agent.run()

    all_image_files = [f for f in DOWNLOADS_DIR.iterdir() if f.suffix.lower() in _IMAGE_SUFFIXES]
    new_files = [f for f in all_image_files if f not in existing_files]

    if not new_files:
        raise ImageGenerationError("Browser agent ran but no new image file was downloaded.")

    path = str(sorted(new_files, key=lambda f: f.stat().st_mtime, reverse=True)[0])
    logger.info(f"Image downloaded to: {path}")
    return path


def generate_image_dreamina(prompt: str) -> str:
    try:
        return asyncio.run(_generate_image_via_browser(prompt))
    except ImageGenerationError:
        raise
    except Exception as e:
        raise ImageGenerationError(f"Browser-based Dreamina generation failed: {e}") from e
