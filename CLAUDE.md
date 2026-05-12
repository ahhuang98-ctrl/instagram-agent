# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Projects

- `instagram_agent/` — Python agent that auto-posts AI-generated images to Instagram on a schedule
- `tictactoe.html` — standalone browser game (no build step needed)

---

## instagram_agent — Setup & Commands

All commands run from `instagram_agent/` with the venv activated.

```powershell
# First-time setup
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# Copy and fill in secrets
copy .env.example .env

# Run the agent (blocking — waits for scheduled trigger)
python main.py

# Smoke-test a single posting run without the scheduler
python -c "
from dotenv import load_dotenv; load_dotenv()
from agent.image_generator import generate_image
from agent.image_host import upload_image_url_to_imgbb
from agent.instagram import post_feed
url = upload_image_url_to_imgbb(generate_image('a sunset over the ocean'))
print(post_feed(url, 'test post'))
"
```

To trigger the job immediately without waiting for the cron time, temporarily set `config.yaml` to `mode: interval` with `minutes: 1`.

---

## Architecture

### Posting pipeline (runs on each scheduled tick)

```
PromptManager (config.yaml)
  → generate_image()      fal.ai Dreamina V3.1  → temporary URL
  → upload_image_url_to_imgbb()  imgbb.com       → permanent public URL
  → post_feed() / post_story()   Instagram Graph API v21.0
```

The imgbb re-hosting step is mandatory: Instagram's Graph API fetches the image asynchronously from the URL you supply, and fal.ai temporary URLs expire before Instagram completes the fetch.

### Key architectural decisions

**`config.yaml` is re-read on every job run** (`main.py:22`). You can edit prompts, captions, or toggle `post_feed`/`post_stories` while the agent is running without restarting it.

**`load_dotenv()` must be called before any `agent.*` import** (`main.py:6`). `fal_client` reads `FAL_KEY` from the environment on module load, so the import order matters.

**Feed and story failures are independent** — each is wrapped in its own try/except in `run_posting_job()`. A failed feed post does not prevent the story from being attempted.

### Instagram Graph API publish flow

Publishing is a two-step process handled in `agent/instagram.py`:
1. `POST /{ig-user-id}/media` — create a media container, get `container_id`
2. `POST /{ig-user-id}/media_publish` — publish the container using `creation_id=container_id`

Stories use the same flow with `media_type=STORIES` added to step 1. Captions are silently ignored by Instagram for Stories.

### Required environment variables

| Variable | Source |
|---|---|
| `FAL_KEY` | fal.ai Dashboard → API Keys |
| `IMGBB_API_KEY` | api.imgbb.com (free account) |
| `INSTAGRAM_USER_ID` | Graph API Explorer: `GET /{page-id}?fields=instagram_business_account` |
| `INSTAGRAM_ACCESS_TOKEN` | Long-lived Page access token (expires every 60 days) |

Instagram posting requires a **Business or Creator account** linked to a **Facebook Page**. Personal accounts are not supported by the Graph API. Required token scopes: `instagram_basic`, `instagram_content_publish`, `pages_show_list`, `pages_read_engagement`.

### Scheduler modes (`config.yaml`)

- `mode: cron` — posts at specific times of day via `CronTrigger` (e.g. `hour: "9,18"`)
- `mode: interval` — posts every N hours/minutes via `IntervalTrigger`

`misfire_grace_time=300` allows jobs that fired up to 5 minutes late to still run (handles brief process sleep/restart).

### Logging

Logs go to both console (INFO+) and `logs/agent.log` (DEBUG+, rotating 5 MB × 3 files). The log file captures full stack traces for all errors; the console shows summary lines only.
