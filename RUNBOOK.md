# jde-ai — Project Runbook

YouTube multi-channel analytics: fetch data, visualise in a dashboard, notify via WhatsApp.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Repository Layout](#2-repository-layout)
3. [One-Time Setup](#3-one-time-setup)
4. [Configuration Reference](#4-configuration-reference)
5. [Channels Configuration](#5-channels-configuration)
6. [Daily Operations](#6-daily-operations)
7. [Dashboard](#7-dashboard)
8. [WhatsApp Notifications](#8-whatsapp-notifications)
9. [Scheduled / Automated Runs](#9-scheduled--automated-runs)
10. [Output Files](#10-output-files)
11. [Troubleshooting](#11-troubleshooting)
12. [Adding a New Channel](#12-adding-a-new-channel)

---

## 1. Project Overview

| Component | File | Purpose |
|---|---|---|
| Data fetcher | `yt_multi_channel.py` | Pulls public stats + recent videos for all channels |
| Dashboard server | `dashboard/serve.py` | Serves analytics UI at localhost:8765 |
| Dashboard UI | `dashboard/index.html` | Charts, stats, video table — runs in browser |
| WhatsApp notifier | `notify_whatsapp.py` | Sends summary to group / individual via Twilio or pywhatkit |
| Channel list | `channels.json` | Editable list of channels to track |
| Single-channel script | `connect-yt.py` | Original OAuth-based single-channel script (legacy) |

**Current channels tracked:**

| Name | Handle | Owned |
|---|---|---|
| Aspirants360 | @aspirants360 | No |
| SimplyTimepass | @simplytimepass | No |
| SimplyEmpressOfficial | @simplyempressofficial | No |
| SimplyCinema | @simplycinema | No |
| SimplyKarur | @simplykarur | No |

---

## 2. Repository Layout

```
jde-ai/
├── yt_multi_channel.py       # Main data-fetch script
├── notify_whatsapp.py        # WhatsApp notification module
├── connect-yt.py             # Legacy single-channel script
├── channels.json             # Channel list (edit to add/remove channels)
├── requirements.txt          # Python dependencies
├── .env                      # API keys & config  ← NOT in git
├── .env.example              # Template for .env
├── .gitignore
├── RUNBOOK.md                # This document
├── dashboard/
│   ├── serve.py              # HTTP server (API + static)
│   └── index.html            # Dashboard UI (Chart.js + Tailwind CDN)
├── reports/                  # Generated JSON + CSV output  ← NOT in git
│   ├── aspirants360_YYYY-MM-DD.json
│   ├── aspirants360_videos_YYYY-MM-DD.csv
│   └── summary_YYYY-MM-DD.csv
├── scripts/
│   └── create_venv.bat       # Windows venv helper
└── venv/                     # Python virtual environment  ← NOT in git
```

---

## 3. One-Time Setup

### 3.1 Python environment

```bat
cd d:\JBDE\SwDevelopment\jde-ai

python -m venv venv
venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 3.2 Google API key

Required for public channel stats (subscribers, views, video count).

1. Go to https://console.cloud.google.com
2. Create a project → **APIs & Services** → **Enable APIs**
3. Enable **YouTube Data API v3**
4. **Credentials** → **Create credentials** → **API Key**
5. Copy the key into `.env`:
   ```
   YOUTUBE_API_KEY=AIza...
   ```

### 3.3 Twilio WhatsApp (individual notifications)

1. Sign up at https://www.twilio.com
2. Go to **Messaging → Try it out → Send a WhatsApp message**
3. From your WhatsApp, send the join code to **+1 415 523 8886**
4. Fill in `.env`:
   ```
   TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
   TWILIO_WHATSAPP_TO=whatsapp:+91XXXXXXXXXX
   ```

### 3.4 WhatsApp Group notifications (pywhatkit)

1. Open the target group in WhatsApp → **Invite via link** → copy the URL
2. Extract the ID: `https://chat.whatsapp.com/`**`<GROUP_ID>`**
3. Fill in `.env`:
   ```
   WHATSAPP_MODE=group
   WHATSAPP_GROUP_ID=Ln6jwrHRnqR5Fp7OHiCFHf
   ```
4. Make sure **WhatsApp Web** is open and logged in before running

### 3.5 OAuth (owned channels only — detailed analytics)

Only needed if you own a channel and want watch-time / revenue data.

1. Google Cloud Console → **OAuth 2.0 Client IDs** → Desktop app → Download JSON
2. Save as `client_secrets.json` in project root
3. Set `owned: true` for that channel in `channels.json`
4. First run will open a browser for login; token saved to `token.json`

---

## 4. Configuration Reference

File: `.env`

```env
# YouTube Data API v3
YOUTUBE_API_KEY=AIza...

# OAuth (owned channels only)
CLIENT_SECRETS_FILE=client_secrets.json
TOKEN_FILE=token.json

# Date range defaults
DEFAULT_START_DAYS_AGO=30
DEFAULT_END_DAYS_AGO=0

# Twilio (individual WhatsApp)
TWILIO_ACCOUNT_SID=ACxxx
TWILIO_AUTH_TOKEN=xxx
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
TWILIO_WHATSAPP_TO=whatsapp:+91XXXXXXXXXX   # comma-separate for multiple

# Group WhatsApp (pywhatkit)
WHATSAPP_MODE=group          # individual | group
WHATSAPP_GROUP_ID=Ln6jwrHRnqR5Fp7OHiCFHf
```

---

## 5. Channels Configuration

File: `channels.json`

```json
{
  "channels": [
    {
      "name": "Display Name",
      "handle": "@channelhandle",
      "channel_id": "",        // auto-filled on first run
      "owned": false,          // true = OAuth analytics enabled
      "notes": "optional note"
    }
  ]
}
```

Channel IDs are **auto-resolved** from handles on the first run and cached so
subsequent runs skip the lookup API call.

---

## 6. Daily Operations

### Fetch analytics for all channels (last 30 days)

```bat
cd d:\JBDE\SwDevelopment\jde-ai
venv\Scripts\activate
python yt_multi_channel.py
```

### Fetch with custom date range

```bat
python yt_multi_channel.py --start 2025-01-01 --end 2025-03-31
python yt_multi_channel.py --days 90
```

### Fetch + send WhatsApp notification

```bat
python yt_multi_channel.py --notify
```

### Fetch more recent videos per channel

```bat
python yt_multi_channel.py --videos 25
```

### All options

```
--channels    channels.json path   (default: channels.json)
--start       YYYY-MM-DD start date
--end         YYYY-MM-DD end date
--days        N days back from today  (default: 30)
--videos      N recent videos to fetch per channel  (default: 10)
--notify      send WhatsApp after fetching
--notify-to   override recipient number  e.g. +919876543210
```

---

## 7. Dashboard

### Start

```bat
cd d:\JBDE\SwDevelopment\jde-ai
venv\Scripts\activate
python dashboard/serve.py
```

Opens automatically at **http://localhost:8765**

### Custom port

```bat
python dashboard/serve.py --port 9000
```

### Headless (no browser)

```bat
python dashboard/serve.py --no-browser
```

### What the dashboard shows

- **Channel tabs** — one tab per channel
- **Stat cards** — Subscribers, Total Views, Videos, Avg Views/Video
- **Top Videos chart** — Bar chart, views + likes (top 10)
- **Upload activity** — Line chart by year
- **Engagement summary** — totals + engagement rate % across recent videos
- **Videos table** — sortable, searchable, with inline view-count bars

Dashboard auto-refreshes when you click **Refresh** or re-run the fetch script.

---

## 8. WhatsApp Notifications

### Send from latest reports (no re-fetch)

```bat
python notify_whatsapp.py
```

### Send to group

```bat
python notify_whatsapp.py --mode group
```

### Send to specific number

```bat
python notify_whatsapp.py --mode individual --to +919876543210
```

### Send a specific report

```bat
python notify_whatsapp.py --report reports/aspirants360_2026-04-05.json
```

### Group mode behaviour (pywhatkit)

- WhatsApp Web opens in your default browser automatically
- Keep WhatsApp Web **logged in** at all times
- The script waits **20 seconds** for the page to load before sending
- Long reports are split into multiple messages (1 minute apart)
- Do **not** close the browser tab while sending

---

## 9. Scheduled / Automated Runs

### Windows Task Scheduler (recommended)

Create `scripts/run_daily.bat`:
```bat
@echo off
cd /d d:\JBDE\SwDevelopment\jde-ai
call venv\Scripts\activate
python yt_multi_channel.py --notify
```

Then in **Task Scheduler**:
- Trigger: Daily at 08:00 AM
- Action: Start `scripts\run_daily.bat`
- Start in: `d:\JBDE\SwDevelopment\jde-ai`

---

## 10. Output Files

All saved to `reports/` (excluded from git):

| File | Contents |
|---|---|
| `<channel>_YYYY-MM-DD.json` | Full report: public stats + videos + analytics |
| `<channel>_videos_YYYY-MM-DD.csv` | Recent videos table (opens in Excel) |
| `<channel>_analytics_YYYY-MM-DD.csv` | Daily analytics time-series (owned channels only) |
| `summary_YYYY-MM-DD.csv` | One row per channel — subscribers, views, video count |

If a CSV is open in Excel, the script will automatically write a `_2` variant instead of crashing.

---

## 11. Troubleshooting

| Problem | Cause | Fix |
|---|---|---|
| `YOUTUBE_API_KEY not set` | Missing `.env` | Copy `.env.example` → `.env` and add key |
| `PermissionError` on CSV | File open in Excel | Close the file or it saves as `_2` automatically |
| `Could not resolve channel ID` | Bad handle or quota | Check handle spelling in `channels.json` |
| `HttpError 403` | API quota exceeded | Wait 24 h or use a different API key |
| `Twilio: Missing config` | `.env` not filled | Add `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_TO` |
| `pywhatkit: group ID not set` | `.env` missing | Set `WHATSAPP_GROUP_ID` in `.env` |
| WhatsApp Web not sending | Not logged in | Open web.whatsapp.com and scan QR code |
| `ImportError: google libs` | Wrong venv | Run `venv\Scripts\activate` before running scripts |
| Dashboard shows "No reports" | No fetches yet | Run `python yt_multi_channel.py` first |

---

## 12. Adding a New Channel

1. Find the channel handle from its YouTube URL (e.g. `@newchannel`)
2. Edit `channels.json` — add an entry:
   ```json
   {
     "name": "Channel Display Name",
     "handle": "@newchannel",
     "channel_id": "",
     "owned": false
   }
   ```
3. Run `python yt_multi_channel.py` — channel ID auto-resolved and cached
4. Refresh the dashboard — new tab appears automatically

---

*Last updated: April 2026 | Repository: github.com/jbdtechsolutions/jde-ai*
