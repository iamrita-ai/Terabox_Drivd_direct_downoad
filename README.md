
# Serena Drive / TeraBox / Direct Downloader Bot (Render)

Telegram bot that downloads files from:
- Google Drive links
- TeraBox / 1024tera share links (best-effort; may require cookies for some links)
- Direct downloadable links

Then uploads to Telegram with:
- Queue (multiple links in one message)
- Progress bar + ETA (edits every 8 seconds to avoid flood)
- Thumbnails for video/photo/audio/pdf
- ZIP if a share contains multiple files (folder/multi-file case)

---

## Features

| Category | Details |
|---|---|
| Providers | Google Drive, Direct Links, TeraBox/1024tera (best-effort) |
| Queue | Multiple links → processed one-by-one |
| Progress | Downloading + Uploading progress + ETA (8 sec update interval) |
| Upload Type | Videos are sent as **playable** (`send_video`, streaming enabled). Others as documents (keeps extension). |
| Thumbnails | Video / Audio / Image / PDF thumbnail generation |
| ZIP | If multiple files are detected for a link → ZIP and send |
| Groups & Topics | In groups: reply to bot OR mention bot. In Topics: reply-chain keeps same topic. |
| Cleanup | Files deleted from server immediately after upload to save Render disk |
| Logs | Each job queued/completed/failed is sent to LOG_CHANNEL |

---

## Limits

| Plan | Daily Limit | Max File Size | Speed |
|---|---:|---:|---|
| Free | 5 tasks/day | 200 MB | Low (rate-limited for direct links) |
| Premium | Unlimited | 4 GB | High |

> Owners are always treated as Premium.

---

## Commands

### User Commands
- `/start` → intro + buttons
- `/help` → full guide
- `/cancel` → cancel running queue in the same chat/topic
- `/setting` → **Premium only** (target chat, title, thumbnail, reset)

### Owner Commands (Owner only)
- Premium add:
  - `/premium <user_id> <days>`
  - `/premium<user_id> <days>`
  - Reply mode: reply to user → `/premium <days>`
- Premium remove:
  - `/remove_premium <user_id>`
  - `/remove premium<user_id>`
  - Reply mode: reply to user → `/remove_premium`
- Broadcast:
  - Reply to any message → `/broadcast` (same message to all users)
  - Or: `/broadcast Your text here`

---

## Deploy on Render (Docker)

### 1) Create Service
- Render → **New** → **Web Service**
- Select this GitHub repo
- Environment: **Docker**

### 2) Render Settings
- **Health Check Path:** `/healthz`
- Docker Build Context Directory: `.`
- Dockerfile Path: `Dockerfile`
- Docker Command: *(leave empty)*

### 3) Required Environment Variables
Set these in Render → Environment:

| Variable | Required | Example |
|---|---:|---|
| `API_ID` | ✅ | `123456` |
| `API_HASH` | ✅ | `abcd1234...` |
| `BOT_TOKEN` | ✅ | `123:ABC...` |
| `MONGO_URI` | ✅ | `mongodb+srv://user:pass@cluster/db?retryWrites=true&w=majority` |

Optional:
| Variable | Purpose |
|---|---|
| `START_PIC` | /start photo URL or Telegram file_id |
| `PDF_THUMB` | PDF thumbnail override (URL or file_id) |
| `FORCE_SUB_CHANNEL` | Force-sub channel (default `@serenaunzipbot`) |
| `FREE_DAILY_TASK_LIMIT` | default `5` |
| `FREE_MAX_SIZE_MB` | default `200` |
| `PREMIUM_MAX_SIZE_MB` | default `4096` |
| `FREE_MAX_RATE_MBPS` | default `1.0` |
| `REMUX_TO_MP4` | default `1` (improves playable video streaming) |
| `TERABOX_COOKIES` | Cookie header string for TeraBox/1024tera (only if required by link) |

### 4) Deploy
Click **Deploy**.  
After deploy:
- `/healthz` should return 200
- Bot should respond on Telegram `/start`

Your Render URL will be:
`https://<your-service-name>.onrender.com`

---

## TeraBox Notes (Important)
Some TeraBox/1024tera shares do NOT provide direct download links without cookies/signature.
If a link fails, set `TERABOX_COOKIES` in Render.

**Format:**
`name=value; name2=value2; ...`

Only include TeraBox cookies (example names):
- `ndus`
- `ndut_fmv`
- `ndut_fmt`
- `csrfToken`

Do NOT put Google cookies in this env var.

---

## Troubleshooting

### Bot responds “Added to queue” but does nothing
Check Render logs for runner errors.  
Most common: bad link (not direct), or provider blocked.

### Mongo errors
- If URI has special characters in password, URL-encode them.
- Make sure Atlas Network Access allows your Render IP (temporary `0.0.0.0/0` for testing).

### TeraBox fails
Set `TERABOX_COOKIES`. Some shares require login cookies.

---

## Credits / Contact
- Force Sub Channel: https://t.me/serenaunzipbot
- Owner: https://t.me/technicalserena (@Xioqui_xin)
