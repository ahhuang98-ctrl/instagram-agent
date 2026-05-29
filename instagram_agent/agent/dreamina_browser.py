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
        f"Click the Generate button and wait up to 90 seconds for images to appear in the grid. "
        f"Once the images are fully visible, hover over the FIRST generated image to reveal the "
        f"download icon (arrow-down button). Click that download icon to download the full-resolution image. "
        f"If hovering does not reveal a download button, click the first image to open it in a larger view, "
        f"then look for a download button in that view and click it. "
        f"If neither approach produces a download, fall back to execute_javascript with: "
        f"(function(){{"
        f"var imgs=Array.from(document.querySelectorAll('img'))"
        f".filter(i=>i.naturalWidth>200&&i.src&&!i.src.startsWith('data:'))"
        f".sort((a,b)=>b.naturalWidth*b.naturalHeight-a.naturalWidth*a.naturalHeight);"
        f"var src=imgs[0].src;"
        f"fetch(src).then(r=>r.blob()).then(b=>{{var u=URL.createObjectURL(b);"
        f"var a=document.createElement('a');a.href=u;a.download='dreamina_image.jpg';a.click();}});"
        f"}})()"
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

    # Prefer files created during this agent run; fall back to newest overall.
    all_image_files = [f for f in DOWNLOADS_DIR.iterdir() if f.suffix.lower() in _IMAGE_SUFFIXES]
    new_files = [f for f in all_image_files if f not in existing_files]

    candidates = new_files if new_files else all_image_files
    if not candidates:
        raise ImageGenerationError("Browser agent ran but no image file found in downloads folder.")

    path = str(sorted(candidates, key=lambda f: f.stat().st_mtime, reverse=True)[0])
    logger.info(f"Image downloaded to: {path}")
    return path


def generate_image_dreamina(prompt: str) -> str:
    try:
        return asyncio.run(_generate_image_via_browser(prompt))
    except ImageGenerationError:
        raise
    except Exception as e:
        raise ImageGenerationError(f"Browser-based Dreamina generation failed: {e}") from e
