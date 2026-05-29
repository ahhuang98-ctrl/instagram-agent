"""
One-time setup script: log into Dreamina manually so the agent can reuse the session.

Usage:
    python agent/dreamina_login.py

A browser window will open. Log in to Dreamina, then press Enter in this terminal.
The session (cookies) will be saved to browser_profile/ and reused by the agent automatically.
"""
import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

BROWSER_PROFILE_DIR = Path.home() / ".instagram-agent" / "dreamina-profile"


async def main() -> None:
    BROWSER_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Using browser profile directory: {BROWSER_PROFILE_DIR}")

    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir=str(BROWSER_PROFILE_DIR),
            headless=False,
        )
        page = await ctx.new_page()
        await page.goto("https://dreamina.capcut.com")

        print("\nBrowser opened. You have 120 seconds to log in to Dreamina manually.")
        print("Waiting...")
        await asyncio.sleep(120)

        await ctx.close()
        print("\nSession saved. The agent will reuse this login automatically.")


asyncio.run(main())
