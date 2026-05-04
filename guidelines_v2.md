# Instagram Story Bot - V3 Modification Guide

## Overview

This document describes the two targeted changes to make to the existing V2 bot:

1. **Replace OpenAI image generation with Nano Banana**
2. **Caption and image are validated separately through Telegram, in two sequential messages**

Everything else remains unchanged: Google Sheets tracking, Pexels fallback, owned-image source, weekly plan, and rendering pipeline.

---

## What Stays the Same

- Google Sheets as the state store and row schema
- Weekly plan configuration (`config/weekly_plan.yaml`)
- `pexels` and `owned` source types
- Caption generation via OpenAI text (`gpt-4o-mini`)
- Rendering pipeline (`src/render.py`)
- Path handling, settings, and environment variable conventions

---

## Change 1: Replace OpenAI Image Generation with Nano Banana

### Current behavior

In `generate_draft.py`, when `source_type == "openai"`, the bot calls `openai_image.generate_image()`, which uses the `gpt-image-1` model to generate a base64 image.

The environment variable `OPENAI_API_KEY` is used for both text (caption) and image generation.

### New behavior

When `source_type` is `"nanobanana"` (new value for `weekly_plan.yaml`), the bot calls a new module `src/sources/nanobanana_image.py` that calls the Nano Banana API.

The OpenAI key is still required for caption generation. A separate `NANO_BANANA_API_KEY` secret is added for image generation.

### New secret to add

| Secret Name | Purpose |
|---|---|
| `NANO_BANANA_API_KEY` | Nano Banana API key for image generation |

Add this secret to GitHub Actions alongside the existing ones.

### How to get the Nano Banana API key

Use these steps (vendor portal wording can vary slightly):

1. Create an account in the Nano Banana developer dashboard.
2. Verify your email and complete any required billing setup.
3. Open the API section (commonly labeled **API Keys**, **Developer**, or **Credentials**).
4. Create a new key for this project (for example: `instagram-story-bot`).
5. Copy the key once and store it securely in your password manager.
6. Add it to GitHub repository secrets as `NANO_BANANA_API_KEY`.
7. For local testing, add it to your local environment (for example in `.env`, not committed).

Recommended key hygiene:

- Use one key per environment (`dev`, `prod`) when possible.
- Rotate the key if it is ever exposed.
- Do not print the full key in logs.

### New module: `src/sources/nanobanana_image.py`

This module must:

- Accept an `api_key`, a `prompt` string, and an optional `size` parameter
- Accept an optional `input_image` parameter for image-to-image generation
- Call the Nano Banana HTTP API to generate an image
- Return the raw image bytes or a local `Path` after saving
- Raise a descriptive `RuntimeError` if the API call fails
- Follow the same interface contract as the current `openai_image.py` functions so `generate_draft.py` stays clean

The module should support both modes:

- Text-to-image (prompt only)
- Image-to-image (prompt + input image bytes/base64)

Refer to the Nano Banana API documentation for the correct endpoint, authentication header, and request/response format.

### Changes to `generate_draft.py`

1. Import `nanobanana_image` from `src.sources`
2. Read `NANO_BANANA_API_KEY` from environment with `require_env()` — only when at least one day uses `"nanobanana"` as the source (or always read it at startup to fail fast)
3. Add a new `elif source_type == "nanobanana":` branch parallel to the existing `elif source_type == "openai":` branch:
   - Read `ai_prompt` and `image_variations` from the plan (same fields as the OpenAI branch)
    - Resolve one random input image from `assets/owned`
    - Call `nanobanana_image.generate_image(nano_key, ai_prompt, input_image=..., ...)`
   - Save the result to `background_path`
   - Set `attribution = "Generated with Nano Banana"`
4. Keep the `"openai"` branch intact so existing plan entries still work during migration

For input image selection, always use the existing image database at `assets/owned` and randomly pick one file per generation.

If the folder has no supported images (`.jpg`, `.jpeg`, `.png`, `.webp`), raise a clear runtime error.

### Changes to `config/weekly_plan.yaml`

For any day that should now use Nano Banana, change:

```yaml
source: "openai"
```

to:

```yaml
source: "nanobanana"
```

The `ai_prompt` and `image_variations` fields remain exactly the same. No other fields need to change.

Example full day config:

```yaml
monday:
    topic: "Inspiracion floral del lunes"
    source: "nanobanana"
    ai_prompt: "Elegant macro floral composition in pastel palette, vertical 9:16"
    prompt_style: "motivational"
    cta: "Feliz semana"
```

Note: in Nano Banana mode, reference images are always selected randomly from `assets/owned`.

### Changes to `requirements.txt`

Add any HTTP client dependency if Nano Banana requires one not already present. The project already has `requests==2.32.3`, which is sufficient for a plain REST call.

If the Nano Banana SDK ships as a PyPI package, add it with a pinned version.

### What to remove

Do **not** delete `src/sources/openai_image.py` yet. Keep it so days still using `source: "openai"` continue to work.

---

## Change 2: Two-Step Telegram Validation (Caption, Then Image)

### Overview

Instead of generating the image immediately after the caption, the bot now pauses at two checkpoints: one for the caption and one for the image. You validate or correct the caption first, and only after your approval does the image get generated.

### New end-to-end flow

```text
Phase 1 — Daily generation job (runs once per day)
    |
    |-- Load plan for today
    |-- Check Google Sheets: skip if status is not missing or "regenerate"
    |-- Generate caption (OpenAI text)
    |-- Send Caption Message to Telegram:
    |       "Caption for YYYY-MM-DD
    |        Topic: <topic>
    |
    |        <generated caption>
    |
    |        Approve:  /approve_caption YYYY-MM-DD
    |        Modify:   /caption YYYY-MM-DD <your new text>"
    |-- Save row in Google Sheets:
    |       status              = "pending_caption_approval"
    |       caption             = <generated caption>
    |       caption_message_id  = <Telegram message ID>
    |-- STOP. No image is generated.

Phase 2 — Approval poller (caption commands, runs every 10–15 min)
    |
    |-- Read last processed update_id from state worksheet
    |-- Fetch new Telegram updates
    |-- For /approve_caption YYYY-MM-DD:
    |       Keep existing caption
    |       Set status = "caption_approved"
    |-- For /caption YYYY-MM-DD <new text>:
    |       Replace caption with <new text> in the sheet
    |       Set status = "caption_approved"
    |-- Persist newest update_id

Phase 3 — Image generation job (runs every 10–15 min)
    |
    |-- Scan Google Sheets for rows with status = "caption_approved"
    |-- For each such row:
    |       Read source_type, ai_prompt, and approved caption from the sheet
    |       Fetch or generate background image
    |       Render the story using the approved caption
    |       Send Image Message to Telegram:
    |               "Image for YYYY-MM-DD
    |                Caption: <approved caption>
    |
    |                Approve:     /approve YYYY-MM-DD
    |                Regenerate:  /regen YYYY-MM-DD
    |                Reject:      /reject YYYY-MM-DD"
    |       Update row:
    |               status              = "pending_image_approval"
    |               telegram_message_id = <image message ID>
    |               telegram_file_id    = <file_id>
    |               attribution         = <source>

Phase 4 — Approval poller (image commands, same run as Phase 2)
    |
    |-- For /approve YYYY-MM-DD:
    |       Set status = "approved"
    |-- For /regen YYYY-MM-DD:
    |       Set status = "caption_approved"  <- re-triggers Phase 3
    |-- For /reject YYYY-MM-DD:
    |       Set status = "rejected"
```

### New and changed Telegram commands

| Command | When to use | Effect |
|---|---|---|
| `/approve_caption YYYY-MM-DD` | After receiving Caption Message | Keeps generated caption, queues image generation |
| `/caption YYYY-MM-DD <new text>` | After receiving Caption Message | Replaces caption with your text, queues image generation |
| `/approve YYYY-MM-DD` | After receiving Image Message | Marks story as fully approved |
| `/regen YYYY-MM-DD` | After receiving Image Message | Keeps caption, regenerates image |
| `/reject YYYY-MM-DD` | Any time | Marks story as rejected, stops the flow |

`/approve` now exclusively governs image approval. Caption approval uses the new `/approve_caption` command.

### New Google Sheets status values

| Status | Meaning |
|---|---|
| `pending_caption_approval` | Caption sent to Telegram, waiting for your input |
| `caption_approved` | Caption confirmed, image generation queued |
| `pending_image_approval` | Image sent to Telegram, waiting for your input |
| `approved` | Story fully approved, ready to publish |
| `rejected` | Story rejected |
| `regenerate` | (existing) Forces a full re-run of the daily job |

### New Google Sheets column

Add one column to the existing schema, after `telegram_file_id`:

| Column | Purpose |
|---|---|
| `caption_message_id` | Telegram message ID of the Caption Message, for reference |

All other existing columns remain unchanged.

### GitHub Actions workflow changes

The current two-workflow setup becomes three workflows:

| Workflow file | Schedule | Responsibility |
|---|---|---|
| `generate_daily.yml` | Once per day | Generate caption, send Caption Message, write row |
| `generate_image.yml` | Every 10–15 min | Scan for `caption_approved` rows, generate image, send Image Message |
| `poll_approvals.yml` | Every 10–15 min | Process all Telegram commands, update sheet statuses |

`generate_image.yml` and `poll_approvals.yml` share the same cron schedule. The order of execution within the same minute is not guaranteed, which is fine because they operate on different status values.

### Changes to `src/generate_draft.py`

**Phase 1 changes (existing `main()` function):**

1. Remove everything after caption generation (image fetch, render, Telegram send).
2. After generating the caption, send one Telegram text-only message containing the caption and the two command instructions.
3. Save the row immediately with `status = "pending_caption_approval"` and `caption_message_id`.
4. Exit. Do not generate any image.

**New entrypoint for Phase 3 — `src/generate_image.py` (new file):**

1. Query Google Sheets for rows with `status == "caption_approved"`.
2. For each row, read `source_type`, `ai_prompt`, and the approved `caption` from the sheet.
3. Fetch or generate the background image using the same `if/elif` branch logic as the original `generate_draft.py`.
4. Render the story using the approved caption.
5. Send the rendered image to Telegram with approve / regen / reject instructions.
6. Update the row: `status = "pending_image_approval"`, `telegram_message_id`, `telegram_file_id`, `attribution`.

### Changes to `src/poll_telegram.py`

Add handling for two new commands:

```text
/approve_caption YYYY-MM-DD
    -> sheet.update_row_status(date, "caption_approved")
    -> no other side effect

/caption YYYY-MM-DD <new text>
    -> strip and store <new text> as the new caption in the sheet
    -> sheet.update_row(date, caption=new_text, status="caption_approved")
```

Modify `/regen` handling:

```text
/regen YYYY-MM-DD
    -> set status = "caption_approved"  (re-queues image generation, keeps caption)
```

Keep `/approve` and `/reject` behavior unchanged.

### Security rule for `/caption` command

The `/caption` command accepts free text from Telegram. Apply the same chat ID guard that already exists for all other commands — only messages from `TELEGRAM_CHAT_ID` are processed. The free text is stored as a plain string in Google Sheets; no shell execution or templating is involved.

---

## Change 3: Anti-Repetition Randomization (Caption + Image)

### Goal

Prevent near-duplicate captions and images from repeating every week, while preserving each weekday topic.

### Randomness strategy

Apply controlled randomness in two places:

1. **Caption randomness (Phase 1):**
     - Use random picks from multiple prompt components in `weekly_plan.yaml` (tone, hook, CTA style, wording hint).
     - Keep existing topic fixed for the day, but vary language framing.
2. **Image randomness (Phase 3):**
     - Continue selecting a random reference image from `assets/owned`.
     - Add random visual modifiers (composition, lighting, camera distance, mood) to the Nano Banana prompt.

### Weekly plan fields to add

Add optional lists in each weekday block (single string still allowed for backward compatibility):

```yaml
caption_hooks:
    - "Pregunta directa"
    - "Frase corta inspiracional"
    - "Tip rapido"

caption_tones:
    - "calido"
    - "elegante"
    - "jugueton"

cta_variations:
    - "Escribenos para pedir"
    - "Te leemos en mensajes"
    - "Quieres uno para regalar?"

image_moods:
    - "airy editorial"
    - "dreamy macro"
    - "clean minimal"

image_compositions:
    - "close-up with negative space"
    - "top-view still life"
    - "soft side angle"
```

Use random selection per run from these lists. If a field is absent, fall back to current defaults.

### Uniqueness guardrail (required)

Before finalizing a caption or image prompt, compare against recent history from Google Sheets (lookback window: last 21 days):

- If caption is equal (case-insensitive) or highly similar to a recent one, regenerate caption once with a stronger variation hint.
- If image prompt signature is repeated recently, re-roll modifiers and select a different random owned image.

If similarity still remains high after one retry, allow manual decision through Telegram caption approval (do not hard-fail the job).

### Metadata to persist in Google Sheets

Add these columns:

| Column | Purpose |
|---|---|
| `generation_attempt` | Attempt number for current date (`1`, `2`, ...), increment on `/regen` |
| `reference_image_name` | Filename chosen from `assets/owned` |
| `caption_fingerprint` | Normalized hash/fingerprint of final caption |
| `image_fingerprint` | Fingerprint of final image prompt signature |

These fields make randomness auditable and help prevent repeating patterns.

### Deterministic random seed (recommended)

Use a seed based on date and attempt for reproducibility:

```text
seed = hash("YYYY-MM-DD" + ":" + generation_attempt)
```

Benefits:

- Regular runs are reproducible for debugging.
- `/regen` changes `generation_attempt`, producing a new random combination.

### Changes to Phase 1 (`generate_draft.py`)

1. Build randomized caption inputs from plan lists.
2. Generate caption.
3. Compute `caption_fingerprint` and compare with last 21 days.
4. If too similar, regenerate once with a stronger variation hint.
5. Save final caption and fingerprint to the sheet.

### Changes to Phase 3 (`generate_image.py`)

1. Select random reference image from `assets/owned`.
2. Randomize prompt modifiers from `image_moods` and `image_compositions`.
3. Compute `image_fingerprint` from: base prompt + modifiers + reference image filename.
4. If repeated in recent history, re-roll once.
5. Save `reference_image_name` and `image_fingerprint` in the sheet.

---

## Updated Environment Variables Reference

| Variable | Used by | Required |
|---|---|---|
| `OPENAI_API_KEY` | Caption generation (`gpt-4o-mini`) | Always |
| `NANO_BANANA_API_KEY` | Nano Banana image generation | When any day uses `nanobanana` source |
| `PEXELS_API_KEY` | Pexels image search | When any day uses `pexels` source |
| `TELEGRAM_BOT_TOKEN` | Telegram messaging | Always |
| `TELEGRAM_CHAT_ID` | Telegram messaging | Always |
| `GOOGLE_CREDENTIALS` | Google Sheets auth | Always |
| `GOOGLE_SHEET_ID` | Google Sheets target | Always |

### Local setup note for `NANO_BANANA_API_KEY`

PowerShell example for local testing:

```powershell
$env:NANO_BANANA_API_KEY = "your_real_key_here"
```

GitHub Actions example (already covered conceptually in this guide):

- Repository Settings -> Secrets and variables -> Actions -> New repository secret
- Name: `NANO_BANANA_API_KEY`
- Value: your Nano Banana key

---

## Implementation Order

Follow this order to minimize risk:

1. **Create `src/sources/nanobanana_image.py`** — implement and unit-test it in isolation before touching `generate_draft.py`
2. **Add `NANO_BANANA_API_KEY` secret** — add it locally in `.env` for testing, then add to GitHub Actions
3. **Add the `"nanobanana"` branch in `generate_draft.py`** — keep the `"openai"` branch untouched
4. **Update `weekly_plan.yaml`** — change one day first, test end-to-end, then update the rest
5. **Add Nano Banana image-input support** — implement random reference selection from `assets/owned`
6. **Split `generate_draft.py`** — Phase 1 sends caption only; extract image generation into new `src/generate_image.py`
7. **Update `poll_telegram.py`** — add `/approve_caption` and `/caption` command handlers, modify `/regen`
8. **Add `generate_image.yml` workflow** — new GitHub Actions workflow scanning for `caption_approved` rows
9. **Add anti-repetition metadata columns** — `generation_attempt`, `reference_image_name`, `caption_fingerprint`, `image_fingerprint`
10. **Add `caption_message_id` column to Google Sheets** — insert it after `telegram_file_id` in the header row
11. **Run local test end-to-end** — manually trigger Phase 1, send `/approve_caption`, confirm Phase 3 runs, send `/approve`

---

## Testing Checklist

**Nano Banana (Change 1):**
- [ ] `nanobanana_image.generate_image()` returns valid image bytes for a known prompt
- [ ] Saving the image to `output/background_YYYY-MM-DD.png` works
- [ ] The `"nanobanana"` branch in `generate_draft.py` is reached when the plan specifies it
- [ ] `attribution` is set to `"Generated with Nano Banana"` in the Google Sheets row
- [ ] Nano Banana always picks a random reference image from `assets/owned`
- [ ] When input image is missing or invalid, the error message is explicit
- [ ] Days using `source: "pexels"` or `source: "owned"` are unaffected
- [ ] Days still using `source: "openai"` continue to work

**Two-step Telegram validation (Change 2):**
- [ ] Phase 1: Caption Message is sent to Telegram with `/approve_caption` and `/caption` instructions
- [ ] Phase 1: Row is saved with `status = "pending_caption_approval"` and `caption_message_id`
- [ ] Phase 1: No image is generated during the daily job
- [ ] Poller: `/approve_caption YYYY-MM-DD` sets status to `caption_approved`, caption unchanged
- [ ] Poller: `/caption YYYY-MM-DD <new text>` stores new text in sheet and sets status to `caption_approved`
- [ ] Poller: Only messages from `TELEGRAM_CHAT_ID` trigger any state change
- [ ] Phase 3: Image generation job detects `caption_approved` rows and generates the image
- [ ] Phase 3: Image Message is sent to Telegram with `/approve`, `/regen`, `/reject` instructions
- [ ] Phase 3: Row is updated with `status = "pending_image_approval"`, `telegram_file_id`, `attribution`
- [ ] Poller: `/approve YYYY-MM-DD` sets status to `approved`
- [ ] Poller: `/regen YYYY-MM-DD` sets status back to `caption_approved`, re-triggering image generation
- [ ] Poller: `/reject YYYY-MM-DD` sets status to `rejected`
- [ ] Running Phase 1 twice for the same date does not create a duplicate row

**Anti-repetition randomization (Change 3):**
- [ ] Caption generation uses randomized plan components (`caption_hooks`, `caption_tones`, `cta_variations`)
- [ ] Image generation uses randomized visual modifiers (`image_moods`, `image_compositions`)
- [ ] Random reference image is selected from `assets/owned` and filename is stored as `reference_image_name`
- [ ] Caption similarity check runs against last 21 days and retries once when too similar
- [ ] Image prompt fingerprint check runs against last 21 days and retries once when repeated
- [ ] `caption_fingerprint` and `image_fingerprint` are saved in the sheet
- [ ] `/regen` increments `generation_attempt` and results in a different random combination
