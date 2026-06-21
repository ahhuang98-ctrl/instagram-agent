# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

GitHub repo: `github.com/ahhuang98-ctrl/instagram-agent`
Local folder: `instagram-agent/`

## Project

Python agent that auto-posts AI-generated images to Instagram on a configurable schedule.

---

## Setup & Commands

All agent commands run from `instagram_agent/` (not repo root) because `main.py` opens `config.yaml` via a relative path. The venv lives at the repo root.

> **Note:** `python` on this machine maps to a Windows Store stub (not a real installation). Python must be installed before the venv setup below will work. As a temporary workaround, the LibreOffice bundled interpreter at `C:\Program Files\LibreOffice\program\python.exe` can run one-off scripts (e.g. the weekly-report generator).

```powershell
# First-time setup (run from repo root)
python -m venv venv
venv\Scripts\activate

# Install packages — browser-use==0.10.1 in requirements.txt pins aiohttp==3.12.15
# which has no prebuilt Windows wheel and fails to build without MSVC.
# Install core packages first, then browser-use at a newer version:
pip install fal-client requests APScheduler python-dotenv PyYAML pytz tenacity pillow
pip install "browser-use>=0.11.0"

# Install the browser-use Chromium browser (NOT the playwright CLI browser)
python -m browser_use.install_browser

# Copy and fill in secrets
copy .env.example .env

# Run the agent (blocking — waits for scheduled trigger; run from instagram_agent/)
cd instagram_agent
python main.py

# Run a single posting job without the scheduler (from instagram_agent/)
python -c "
from dotenv import load_dotenv; load_dotenv()
import sys; sys.path.insert(0, '.')
from main import run_posting_job
run_posting_job()
"
```

To trigger the job immediately without waiting for the cron time, temporarily set `config.yaml` to `mode: interval` with `minutes: 1`.

---

## Architecture

### Posting pipeline (runs on each scheduled tick)

```
PromptManager (config.yaml)
  → generate_image()      dreamina_browser (browser-use + CDP) → local file path
                       OR fal.ai Dreamina V3.1                 → temporary URL
  → upload_*_to_imgbb()  imgbb.com  → permanent public URL
  → post_feed()          Instagram Graph API v25.0
```

The imgbb re-hosting step is mandatory: Instagram's Graph API fetches the image asynchronously from the URL you supply, and source URLs (fal.ai temp URLs, Dreamina CDN) expire or are auth-gated before Instagram completes the fetch.

**Active generator:** `dreamina_browser` (set in `config.yaml`). The `fal` generator requires a funded fal.ai account (balance was exhausted as of 2026-05-29).

**`dreamina_browser` download mechanism:** After the browser agent confirms images are visible in the Dreamina grid, `page.evaluate()` scrapes all `ibyteimg.com` `<img>` src URLs from the DOM, sorts them by intrinsic pixel area (largest first), then downloads the highest-resolution image via Python `requests`. WebP images are automatically converted to JPEG via Pillow before upload. This avoids relying on the browser's download button (which is unreliable in browser-use).

**browser-use LLM import:** `dreamina_browser` uses `browser_use.llm.anthropic.chat.ChatAnthropic`, not `langchain_anthropic.ChatAnthropic`. The browser-use version checks `llm.provider` internally; only its own wrapper exposes that attribute.

### Key architectural decisions

**`config.yaml` is re-read on every job run** (`main.py:22`). You can edit prompts, captions, or toggle `post_feed`/`post_stories` while the agent is running without restarting it.

**`load_dotenv()` must be called before any `agent.*` import** (`main.py:6`). `fal_client` reads `FAL_KEY` from the environment on module load, so the import order matters. The `dreamina_browser` generator reads credentials lazily (`os.environ[...]` at call time), so it's less sensitive to order, but calling `load_dotenv()` first is still required.

**Feed and story failures are independent** — each is wrapped in its own try/except in `run_posting_job()`. A failed feed post does not prevent the story from being attempted.

### Instagram Graph API publish flow

Publishing is a two-step process handled in `agent/instagram.py`:
1. `POST /{ig-user-id}/media` — create a media container, get `container_id`
2. `POST /{ig-user-id}/media_publish` — publish the container using `creation_id=container_id`

Stories use the same flow with `media_type=STORIES` added to step 1. Captions are silently ignored by Instagram for Stories.

### Required environment variables

| Variable | Source | Required for |
|---|---|---|
| `IMGBB_API_KEY` | api.imgbb.com (free account) | all generators |
| `INSTAGRAM_USER_ID` | Graph API Explorer: `GET /{page-id}?fields=instagram_business_account` | posting |
| `INSTAGRAM_ACCESS_TOKEN` | Long-lived Page access token (expires every 60 days) | posting |
| `DREAMINA_EMAIL` | CapCut/Dreamina account email | `generator: dreamina_browser` |
| `DREAMINA_PASSWORD` | CapCut/Dreamina account password | `generator: dreamina_browser` |
| `ANTHROPIC_API_KEY` | console.anthropic.com → API Keys | `generator: dreamina_browser` (LLM for browser agent) |
| `FAL_KEY` | fal.ai Dashboard → API Keys | `generator: fal` only (inactive — balance exhausted) |

Instagram posting requires a **Business or Creator account** linked to a **Facebook Page**. Personal accounts are not supported by the Graph API. Required token scopes: `instagram_basic`, `instagram_content_publish`, `pages_show_list`, `pages_read_engagement`.

### Scheduler modes (`config.yaml`)

- `mode: cron` — posts at specific times of day via `CronTrigger` (e.g. `hour: "9,18"`)
- `mode: interval` — posts every N hours/minutes via `IntervalTrigger`

`misfire_grace_time=300` allows jobs that fired up to 5 minutes late to still run (handles brief process sleep/restart).

### Logging

Logs go to both console (INFO+) and `logs/agent.log` (DEBUG+, rotating 5 MB × 3 files). The log file captures full stack traces for all errors; the console shows summary lines only.

---

## Claude Code Skills

Slash commands available in `.claude/commands/`:

| Skill | Usage | Description |
|---|---|---|
| `/weekly-report` | `/weekly-report 2026-05-11 2026-05-17` | Pulls GitHub commits/PRs/issues for the date range and writes a `.docx` report. Uses LibreOffice Python if standalone Python is unavailable. |
| `/python-bugfix` | `/python-bugfix <error or description>` | Diagnoses a Python traceback or bug report, finds the root cause, and applies a minimal targeted fix. |
| `/python-dev` | `/python-dev <task description>` | Writes new Python modules, functions, or scripts following project conventions (type hints, PEP 8, minimal comments). |
