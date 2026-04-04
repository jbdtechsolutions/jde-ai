"""
notify_whatsapp.py
------------------
Send YouTube analytics summaries to WhatsApp via Twilio.

Setup (one-time):
  1. Sign up at https://www.twilio.com (free trial works)
  2. Go to Messaging → Try it out → Send a WhatsApp message
  3. Join the sandbox: send the join code from your WhatsApp to +1 415 523 8886
  4. Add the 3 Twilio vars to your .env file (see .env.example)

Usage (standalone):
  python notify_whatsapp.py                        # notify from latest reports
  python notify_whatsapp.py --report reports/x.json

Called automatically by yt_multi_channel.py --notify
"""

import os
import sys
import json
import pathlib
import datetime
import argparse

from dotenv import load_dotenv

load_dotenv()

try:
    from twilio.rest import Client as TwilioClient
except ImportError:
    print("Twilio not installed. Run:  pip install twilio")
    sys.exit(1)


# ── config ─────────────────────────────────────────────────────────────────────

REPORTS_DIR = pathlib.Path("reports")

TWILIO_SID      = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN    = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM     = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")  # sandbox default
TWILIO_TO       = os.getenv("TWILIO_WHATSAPP_TO")   # your number e.g. whatsapp:+919876543210


# ── formatters ─────────────────────────────────────────────────────────────────

def fmt(n):
    if n is None:
        return "—"
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return f"{n:,}"


def build_message(reports: list[dict], date_label: str) -> str:
    """Build a WhatsApp-friendly analytics summary message."""
    lines = []
    lines.append(f"📊 *YouTube Analytics Report*")
    lines.append(f"🗓 _{date_label}_")
    lines.append("")

    for r in reports:
        ps     = r.get("public_stats", {})
        videos = r.get("recent_videos", [])
        name   = r.get("channel", "Unknown")

        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"📺 *{name}*")
        lines.append(f"👥 Subscribers : *{fmt(ps.get('subscriber_count'))}*")
        lines.append(f"👁 Total Views  : *{fmt(ps.get('view_count'))}*")
        lines.append(f"🎬 Videos       : *{fmt(ps.get('video_count'))}*")

        if ps.get("video_count") and ps.get("view_count"):
            avg = ps["view_count"] // ps["video_count"]
            lines.append(f"📈 Avg Views/Video : *{fmt(avg)}*")

        if videos:
            # engagement stats over recent videos
            total_views    = sum(v.get("view_count", 0)    for v in videos)
            total_likes    = sum(v.get("like_count", 0)    for v in videos)
            total_comments = sum(v.get("comment_count", 0) for v in videos)

            lines.append("")
            lines.append(f"_Recent {len(videos)} videos_")
            lines.append(f"  👁 Views    : {fmt(total_views)}")
            lines.append(f"  👍 Likes    : {fmt(total_likes)}")
            lines.append(f"  💬 Comments : {fmt(total_comments)}")

            # top video by views
            top = max(videos, key=lambda v: v.get("view_count", 0))
            title = top["title"]
            if len(title) > 50:
                title = title[:47] + "…"
            lines.append("")
            lines.append(f"🔥 *Top Video*")
            lines.append(f'  "{title}"')
            lines.append(f"  👁 {fmt(top['view_count'])} views  👍 {fmt(top['like_count'])} likes")
            lines.append(f"  {top['url']}")

        lines.append("")

    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("_Sent by jde-ai · YouTube Analytics_")
    return "\n".join(lines)


# ── sender ──────────────────────────────────────────────────────────────────────

def send_whatsapp(message: str, to: str = None) -> bool:
    """Send message via Twilio WhatsApp. Returns True on success."""
    sid   = TWILIO_SID
    token = TWILIO_TOKEN
    from_ = TWILIO_FROM
    to_   = to or TWILIO_TO

    missing = [k for k, v in {
        "TWILIO_ACCOUNT_SID": sid,
        "TWILIO_AUTH_TOKEN":  token,
        "TWILIO_WHATSAPP_TO": to_,
    }.items() if not v]

    if missing:
        print(f"[ERROR] Missing Twilio config in .env: {', '.join(missing)}")
        return False

    # ensure whatsapp: prefix
    if not from_.startswith("whatsapp:"):
        from_ = f"whatsapp:{from_}"
    if not to_.startswith("whatsapp:"):
        to_ = f"whatsapp:{to_}"

    try:
        client = TwilioClient(sid, token)
        msg = client.messages.create(body=message, from_=from_, to=to_)
        print(f"  WhatsApp sent  SID: {msg.sid}  status: {msg.status}")
        return True
    except Exception as e:
        print(f"  [ERROR] WhatsApp send failed: {e}")
        return False


# ── report loader ───────────────────────────────────────────────────────────────

def load_latest_reports() -> list[dict]:
    """Load the most recent JSON report per channel from reports/."""
    if not REPORTS_DIR.exists():
        return []

    latest: dict[str, pathlib.Path] = {}
    for f in sorted(REPORTS_DIR.glob("*.json")):
        if any(x in f.name for x in ("_videos_", "_analytics_", "summary")):
            continue
        parts = f.stem.rsplit("_", 1)
        slug = parts[0] if len(parts) == 2 else f.stem
        if slug not in latest or f.name > latest[slug].name:
            latest[slug] = f

    reports = []
    for _, path in sorted(latest.items()):
        try:
            reports.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            pass
    return reports


# ── split long messages ─────────────────────────────────────────────────────────

def split_message(text: str, max_len: int = 1500) -> list[str]:
    """
    WhatsApp has a ~4096 char limit per message.
    We split at 1500 chars on channel boundaries to keep messages readable.
    """
    if len(text) <= max_len:
        return [text]

    parts, chunk = [], []
    for line in text.splitlines(keepends=True):
        if sum(len(l) for l in chunk) + len(line) > max_len and chunk:
            parts.append("".join(chunk).strip())
            chunk = []
        chunk.append(line)
    if chunk:
        parts.append("".join(chunk).strip())
    return parts


# ── main ────────────────────────────────────────────────────────────────────────

def notify(reports: list[dict] = None, to: str = None) -> bool:
    """Public entry point — called from yt_multi_channel.py."""
    if reports is None:
        reports = load_latest_reports()
    if not reports:
        print("  [WARN] No reports to notify about.")
        return False

    date_label = datetime.date.today().strftime("%d %b %Y")
    message = build_message(reports, date_label)

    print(f"\n  Sending WhatsApp notification ({len(reports)} channel(s)) …")

    parts = split_message(message)
    ok = True
    for i, part in enumerate(parts, 1):
        suffix = f" ({i}/{len(parts)})" if len(parts) > 1 else ""
        ok = send_whatsapp(part + suffix, to=to) and ok

    return ok


def main():
    parser = argparse.ArgumentParser(description="Send YouTube analytics to WhatsApp")
    parser.add_argument("--report", help="Specific JSON report file (default: latest in reports/)")
    parser.add_argument("--to",     help="Recipient WhatsApp number e.g. +919876543210")
    args = parser.parse_args()

    if args.report:
        path = pathlib.Path(args.report)
        if not path.exists():
            print(f"File not found: {path}")
            sys.exit(1)
        reports = [json.loads(path.read_text(encoding="utf-8"))]
    else:
        reports = load_latest_reports()
        if not reports:
            print("No reports found. Run python yt_multi_channel.py first.")
            sys.exit(1)

    to = f"whatsapp:{args.to}" if args.to else None
    success = notify(reports, to=to)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
