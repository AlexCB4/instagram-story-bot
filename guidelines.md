# Instagram Story Automation Bot - V2 Setup Guide

## Table of Contents
1. [Overview](#overview)
2. [What Changed in V2](#what-changed-in-v2)
3. [Recommended Architecture](#recommended-architecture)
4. [Prerequisites](#prerequisites)
5. [Project Structure](#project-structure)
6. [Step 1: Create Telegram Bot](#step-1-create-telegram-bot)
7. [Step 2: Setup Google Sheets](#step-2-setup-google-sheets)
8. [Step 3: Get API Keys](#step-3-get-api-keys)
9. [Step 4: Project Setup](#step-4-project-setup)
10. [Step 5: Configure Secrets](#step-5-configure-secrets)
11. [Step 6: Implementation Notes](#step-6-implementation-notes)
12. [Step 7: GitHub Actions Strategy](#step-7-github-actions-strategy)
13. [Step 8: Testing Strategy](#step-8-testing-strategy)
14. [Operational Rules](#operational-rules)
15. [Cost Estimation](#cost-estimation)
16. [Troubleshooting](#troubleshooting)
17. [Next Steps](#next-steps)

---

## Overview

This system generates one Instagram Story draft per day from a weekly content plan, sends the draft to Telegram for approval, and keeps the workflow state in Google Sheets. You still publish manually to Instagram. That is the correct scope for a low-cost automation setup.

The V2 design keeps the original idea but fixes the weak points that would make the first version unreliable in production.

**Primary goals:**
- Generate a daily story draft automatically
- Review and approve it in Telegram
- Keep a durable record of every draft and its status
- Avoid duplicate processing across scheduled runs
- Work predictably in GitHub Actions and on Windows for local testing

---

## What Changed in V2

The first draft of the guide had the right idea but a few structural problems. This version fixes them:

1. **No dependency on GitHub artifact reuse for approvals**
   - GitHub artifacts are not a reliable long-term handoff layer between unrelated scheduled runs.
   - V2 stores durable references in Google Sheets instead.

2. **Telegram polling is idempotent**
   - We persist the last processed `update_id` so approval commands are not processed multiple times.

3. **Paths are resolved from the repository root**
   - No `cd src` assumptions.
   - Python uses `pathlib` and absolute repo-relative paths.

4. **Generated assets get a durable reference**
   - The bot sends the draft to Telegram immediately.
   - We store either the local generated path for same-run operations and the Telegram `file_id` or a durable URL for later retrieval.

5. **Cross-platform file handling**
   - No shell `cp` calls from Python.
   - Use `shutil.copy2()`.

6. **Modern Google auth**
   - Use `google.oauth2.service_account` instead of `oauth2client`.

7. **Duplicate-safe daily generation**
   - The daily job checks if a row for today already exists before creating a new draft.

---

## Recommended Architecture

```text
Daily Scheduler (GitHub Actions)
    |
    |-- Load weekly plan
    |-- Generate or fetch background image
    |-- Generate caption text
    |-- Render story image
    |-- Send draft to Telegram
    |-- Save row in Google Sheets:
          date
          weekday
          topic
          source_type
          status=pending_approval
          caption
          telegram_message_id
          telegram_file_id
          attribution
          notes

Approval Poller (GitHub Actions every 10-15 min)
    |
    |-- Read last processed Telegram update_id from Sheets or state file
    |-- Fetch new Telegram updates with offset
    |-- Parse commands: /approve YYYY-MM-DD, /reject YYYY-MM-DD, /regen YYYY-MM-DD
    |-- Update row status in Google Sheets
    |-- Persist newest processed update_id

You
    |
    |-- Review draft in Telegram
    |-- Approve or reject
    |-- Publish manually to Instagram
```

### Why this version is better

- Google Sheets becomes the source of truth for workflow state.
- Telegram becomes the review interface, not the database.
- GitHub Actions remains stateless between runs, which is fine because the required state is persisted externally.

---

## Prerequisites

- GitHub account
- Telegram account
- Google account
- OpenAI account
- Pexels account (optional but recommended)
- Python 3.11+ for local testing
- Git installed locally

Optional but useful:

- A dedicated brand font
- A small set of owned product photos
- A public brand handle to place on the story

---

## Project Structure

```text
instagram-story-bot/
├── .github/
│   └── workflows/
│       ├── generate_daily.yml
│       └── poll_approvals.yml
├── src/
│   ├── __init__.py
│   ├── settings.py
│   ├── generate_draft.py
│   ├── poll_telegram.py
│   ├── render.py
│   ├── gsheet.py
│   ├── telegram_api.py
│   ├── state_store.py
│   └── sources/
│       ├── __init__.py
│       ├── pexels.py
│       ├── openai_image.py
│       └── openai_text.py
├── config/
│   └── weekly_plan.yaml
├── assets/
│   └── owned/
│       └── .gitkeep
├── fonts/
│   └── Roboto-Bold.ttf
├── output/
│   └── .gitkeep
├── .gitignore
├── requirements.txt
└── README.md
```

### Notes on structure

- `output/` holds generated images during local runs and CI runs.
- `settings.py` centralizes repo-root path handling.
- `state_store.py` manages the last processed Telegram `update_id`.
- `telegram_api.py` isolates Telegram messaging from business logic.

---

## Step 1: Create Telegram Bot

This is the first thing to do because the bot is your approval interface.

### 1.1 Create the Bot

1. Open Telegram.
2. Search for `@BotFather`.
3. Start the chat and send `/newbot`.
4. Choose:
   - Bot name: `My Instagram Story Bot`
   - Username: something unique ending in `bot`, for example `my_ig_story_review_bot`
5. BotFather will return a token that looks like this:

```text
123456789:ABCdefGHIjklMNOpqrsTUVwxyz
```

6. Save this token securely. Later it will be your `TELEGRAM_BOT_TOKEN` GitHub secret.

### 1.2 Open a Chat With Your Bot

1. Search for your new bot username in Telegram.
2. Open the chat.
3. Press `Start` or send `/start`.

This step matters because Telegram will not return private-chat updates for a bot that has never been contacted.

### 1.3 Get Your Chat ID

Open this URL in your browser, replacing `YOUR_BOT_TOKEN` with your real token:

```text
https://api.telegram.org/botYOUR_BOT_TOKEN/getUpdates
```

You are looking for a JSON response with a `chat` object like this:

```json
{
  "ok": true,
  "result": [
    {
      "update_id": 123456789,
      "message": {
        "chat": {
          "id": 987654321,
          "type": "private"
        },
        "text": "/start"
      }
    }
  ]
}
```

Copy the `chat.id` value. That number is your `TELEGRAM_CHAT_ID`.

### 1.4 Confirm Step 1 Is Complete

At the end of Step 1 you should have:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

If `getUpdates` returns an empty `result`, send another message to the bot and refresh the URL.

### 1.5 Recommended command format

Use these commands in Telegram later:

```text
/approve 2026-03-14
/reject 2026-03-14
/regen 2026-03-14
```

The `YYYY-MM-DD` date format should match the row key in Google Sheets.

---

## Step 2: Setup Google Sheets

Google Sheets is the state store for this project. Treat it as the system of record.

### 2.1 Create the Sheet

1. Go to Google Sheets.
2. Create a new spreadsheet named `Instagram Story Queue`.
3. Add these headers in row 1:

```text
date | weekday | topic | source_type | status | caption | telegram_message_id | telegram_file_id | attribution | notes
```

4. Copy the Sheet ID from the URL:

```text
https://docs.google.com/spreadsheets/d/SHEET_ID_HERE/edit
```

### 2.2 Create a Google Service Account

1. Open Google Cloud Console.
2. Create a project or select an existing one.
3. Enable the Google Sheets API.
4. Create a Service Account.
5. Create a JSON key for that service account.
6. Download the JSON file and keep it secure.

### 2.3 Share the Sheet With the Service Account

1. Open the downloaded JSON file.
2. Copy the `client_email` value.
3. Open your Google Sheet.
4. Share the sheet with that email as `Editor`.

### 2.4 Add a State Sheet or State Row

You need one place to store the last Telegram offset.

Recommended options:

1. Create a second worksheet named `state` with headers:

```text
key | value
```

Then add this row:

```text
telegram_last_update_id | 0
```

2. If you want a simpler setup, keep a dedicated state row in the main sheet, but a second worksheet is cleaner.

---

## Step 3: Get API Keys

### 3.1 OpenAI API Key

1. Go to the OpenAI dashboard.
2. Create a new API key.
3. Save it securely as `OPENAI_API_KEY`.

### 3.2 Pexels API Key

1. Go to the Pexels API page.
2. Create an account if needed.
3. Copy your API key.
4. Save it as `PEXELS_API_KEY`.

If you plan to use only your own photos at first, you can delay Pexels setup.

---

## Step 4: Project Setup

### 4.1 Create Repository

1. Create a GitHub repository named `instagram-story-bot`.
2. Clone it locally.

### 4.2 Create Directory Structure

```bash
mkdir .github
mkdir .github\workflows
mkdir src
mkdir src\sources
mkdir config
mkdir assets
mkdir assets\owned
mkdir fonts
mkdir output
type nul > src\__init__.py
type nul > src\sources\__init__.py
type nul > assets\owned\.gitkeep
type nul > output\.gitkeep
```

### 4.3 Create `.gitignore`

Recommended entries:

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/
.venv/
venv/

# Local secrets
.env
*.json
secrets/

# Generated files
output/*.png
output/*.jpg
draft_info.txt

# IDE
.vscode/
.idea/

# OS
Thumbs.db
.DS_Store
```

### 4.4 Create `requirements.txt`

Recommended packages:

```text
openai==1.68.2
requests==2.32.3
Pillow==11.1.0
gspread==6.2.0
google-auth==2.38.0
PyYAML==6.0.2
```

`python-telegram-bot` is optional for this setup because plain HTTP requests are enough for a lightweight approval bot.

---

## Step 5: Configure Secrets

Add these GitHub Actions secrets:

| Secret Name | Purpose |
|-------------|---------|
| `TELEGRAM_BOT_TOKEN` | Telegram bot token |
| `TELEGRAM_CHAT_ID` | Your private chat ID |
| `OPENAI_API_KEY` | OpenAI text and image generation |
| `PEXELS_API_KEY` | Pexels image search |
| `GOOGLE_SHEET_ID` | Main Google Sheet ID |
| `GOOGLE_CREDENTIALS` | Full JSON contents of the service account key |

For `GOOGLE_CREDENTIALS`, paste the entire JSON document as the secret value.

---

## Step 6: Implementation Notes

This section defines the rules the code should follow when you build it.

### 6.1 Path handling

- Do not rely on the current working directory.
- Use `pathlib.Path(__file__).resolve()` to derive the repo root.
- Build all file paths relative to the repo root.

### 6.2 Daily generation flow

1. Load `weekly_plan.yaml`.
2. Determine today's plan.
3. Check Google Sheets for an existing row with today's date.
4. If a row already exists and status is not `regenerate`, skip creation.
5. Generate or fetch the image.
6. Generate caption text.
7. Render the story to `output/story_YYYY-MM-DD.png`.
8. Send the image to Telegram.
9. Save the resulting `message_id` and `file_id` in Google Sheets.
10. Mark status as `pending_approval`.

### 6.3 Approval flow

1. Read `telegram_last_update_id` from the state worksheet.
2. Call Telegram `getUpdates` with `offset = last_update_id + 1`.
3. Process only matching commands from your allowed chat ID.
4. Update the corresponding row status.
5. Save the newest processed update ID back to the state worksheet.

### 6.4 Security rules

- Never commit credentials JSON into the repo.
- Never log full tokens.
- Validate the incoming Telegram chat ID before processing commands.

### 6.5 Minimum row schema

The main sheet should hold at least these fields:

```text
date
weekday
topic
source_type
status
caption
telegram_message_id
telegram_file_id
attribution
notes
```

---

## Step 7: GitHub Actions Strategy

### 7.1 Daily Workflow

Run once per day.

Responsibilities:

- Install dependencies
- Download or verify font
- Generate draft
- Send draft to Telegram
- Update Google Sheets

### 7.2 Polling Workflow

Run every 10 to 15 minutes.

Responsibilities:

- Read persisted Telegram offset
- Fetch only new updates
- Process commands safely
- Update Google Sheets status

### 7.3 Important workflow rule

Do not design the system around reusing a previous run artifact in a later scheduled run. Store durable metadata externally instead.

---

## Step 8: Testing Strategy

### 8.1 Local testing order

1. Test Telegram connectivity
2. Test Google Sheets authentication
3. Test one image source at a time
4. Test rendering with a local sample image
5. Test daily generation without scheduling
6. Test polling with a manual `/approve YYYY-MM-DD` message

### 8.2 What to verify

- One row is created per date
- Duplicate runs do not create duplicates
- Telegram commands are processed only once
- The correct row status is updated
- The generated image renders at `1080x1920`

---

## Operational Rules

These rules prevent the system from drifting into unreliable behavior.

1. Use Google Sheets as the source of truth.
2. Treat Telegram as an interface, not a database.
3. Persist offsets for all polled APIs.
4. Prefer idempotent jobs.
5. Do not depend on local runner files after a workflow run finishes.
6. Keep one unique row per story date.

---

## Cost Estimation

Approximate monthly cost for 30 stories:

| Service | Estimated Cost |
|---------|----------------|
| GitHub Actions public repo | $0 |
| GitHub Actions private repo | Low, depends on usage |
| OpenAI text generation | Very low |
| OpenAI image generation | Main variable cost |
| Pexels | $0 |
| Telegram | $0 |
| Google Sheets | $0 |

If you want to keep costs near zero:

- Prefer Pexels and owned images
- Use OpenAI-generated images only on selected days
- Keep captions short and simple

---

## Troubleshooting

### `getUpdates` returns empty results

- Send `/start` to the bot first
- Make sure you are using the correct bot token

### Telegram commands keep reprocessing

- Your last processed `update_id` is not being persisted correctly
- Verify the `state` worksheet is being updated

### Sheet authentication fails

- Confirm the full credentials JSON is in `GOOGLE_CREDENTIALS`
- Confirm the sheet is shared with the service account email

### Draft image exists locally but cannot be found later

- That is expected if you only stored a runner-local path
- Store `telegram_file_id` or another durable external reference instead

### Workflow behaves differently locally and in CI

- Check path handling first
- Avoid shell-specific commands in Python code

---

## Next Steps

After this guide is in place, follow this order:

1. Complete Step 1 and confirm you have `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.
2. Complete Step 2 so Google Sheets is ready to persist state.
3. Only then start writing the Python code.
4. Add the GitHub Actions secrets before running the workflows.

---

## Step 1 Checklist

Before moving on, confirm these are done:

- Bot created in BotFather
- You sent `/start` to the bot
- You retrieved `TELEGRAM_BOT_TOKEN`
- You retrieved `TELEGRAM_CHAT_ID`

If you want to proceed interactively, the next action is simple: create the Telegram bot first, then send me either:

1. `I have the bot token but not the chat ID`
2. `I have both the bot token and chat ID`
3. `I got stuck at BotFather`
