"""
notify_whatsapp.py
------------------
Send YouTube analytics summaries to WhatsApp.

Two modes (set WHATSAPP_MODE in .env):

  individual  (default) — Twilio API, sends to one or more phone numbers
  group                 — pywhatkit, sends to a WhatsApp group via WhatsApp Web

Individual setup:
  WHATSAPP_MODE=individual
  TWILIO_ACCOUNT_SID=ACxxx
  TWILIO_AUTH_TOKEN=xxx
  TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
  TWILIO_WHATSAPP_TO=whatsapp:+91XXXXXXXXXX,whatsapp:+91YYYYYYYYYY   (comma-separated)

Group setup:
  WHATSAPP_MODE=group
  WHATSAPP_GROUP_ID=AABBCCxxxx   (see how to find it below)

  How to find WHATSAPP_GROUP_ID:
    1. Open WhatsApp Web (web.whatsapp.com) and open the group
    2. Click group name → Invite via link
    3. The link looks like:  https://chat.whatsapp.com/XXXXXXXXXXXXXX
    4. The part after /  is your WHATSAPP_GROUP_ID

Usage:
  python notify_whatsapp.py                   # uses mode from .env
  python notify_whatsapp.py --mode group
  python notify_whatsapp.py --mode individual --to +919876543210
  python notify_whatsapp.py --report reports/aspirants360_2026-04-04.json

Called automatically by:
  python yt_multi_channel.py --notify
"""

import os
import sys
import json
import time
import pathlib
import datetime
import argparse

from dotenv import load_dotenv

load_dotenv()

# ── config ─────────────────────────────────────────────────────────────────────

REPORTS_DIR = pathlib.Path("reports")

WHATSAPP_MODE    = os.getenv("WHATSAPP_MODE", "individual").strip().lower()

# Twilio (individual mode)
TWILIO_SID       = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN     = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM      = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
TWILIO_TO_RAW    = os.getenv("TWILIO_WHATSAPP_TO", "")

# pywhatkit (group mode)
WHATSAPP_GROUP_ID = os.getenv("WHATSAPP_GROUP_ID", "")

# parse comma-separated recipients
def _parse_recipients(raw: str) -> list[str]:
    return [
        r.strip() if r.strip().startswith("whatsapp:") else f"whatsapp:{r.strip()}"
        for r in raw.split(",")
        if r.strip()
    ]

TWILIO_RECIPIENTS = _parse_recipients(TWILIO_TO_RAW)


# ── message formatter ──────────────────────────────────────────────────────────

def fmt(n):
    if n is None:
        return "-"
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return f"{n:,}"


def build_message(reports: list[dict], date_label: str) -> str:
    lines = [
        f"📊 *YouTube Analytics Report*",
        f"🗓 _{date_label}_",
        "",
    ]

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
            total_views    = sum(v.get("view_count", 0)    for v in videos)
            total_likes    = sum(v.get("like_count", 0)    for v in videos)
            total_comments = sum(v.get("comment_count", 0) for v in videos)

            lines += [
                "",
                f"_Recent {len(videos)} videos_",
                f"  👁 Views    : {fmt(total_views)}",
                f"  👍 Likes    : {fmt(total_likes)}",
                f"  💬 Comments : {fmt(total_comments)}",
            ]

            top   = max(videos, key=lambda v: v.get("view_count", 0))
            title = top["title"][:47] + "…" if len(top["title"]) > 50 else top["title"]
            lines += [
                "",
                f"🔥 *Top Video*",
                f'  "{title}"',
                f"  👁 {fmt(top['view_count'])} views  👍 {fmt(top['like_count'])} likes",
                f"  {top['url']}",
            ]

        lines.append("")

    lines += ["━━━━━━━━━━━━━━━━━━━━", "_Sent by jde-ai · YouTube Analytics_"]
    return "\n".join(lines)


def split_message(text: str, max_len: int = 1500) -> list[str]:
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


# ── individual sender (Twilio) ─────────────────────────────────────────────────

def send_individual(message: str, recipients: list[str] = None) -> bool:
    try:
        from twilio.rest import Client as TwilioClient
    except ImportError:
        print("  [ERROR] twilio not installed. Run: pip install twilio")
        return False

    targets = recipients or TWILIO_RECIPIENTS
    missing = [k for k, v in {"TWILIO_ACCOUNT_SID": TWILIO_SID, "TWILIO_AUTH_TOKEN": TWILIO_TOKEN}.items() if not v]
    if missing:
        print(f"  [ERROR] Missing Twilio config: {', '.join(missing)}")
        return False
    if not targets:
        print("  [ERROR] No recipients. Set TWILIO_WHATSAPP_TO in .env")
        return False

    from_  = TWILIO_FROM if TWILIO_FROM.startswith("whatsapp:") else f"whatsapp:{TWILIO_FROM}"
    client = TwilioClient(TWILIO_SID, TWILIO_TOKEN)
    ok     = True

    parts = split_message(message)
    for to in targets:
        print(f"  → Sending to {to} …")
        for i, part in enumerate(parts, 1):
            suffix = f" ({i}/{len(parts)})" if len(parts) > 1 else ""
            try:
                msg = client.messages.create(body=part + suffix, from_=from_, to=to)
                print(f"    Sent  SID={msg.sid}  status={msg.status}")
            except Exception as e:
                print(f"    [ERROR] {e}")
                ok = False
            if len(parts) > 1:
                time.sleep(1)   # avoid rate limit between parts

    return ok


# ── group sender (pywhatkit → WhatsApp Web) ────────────────────────────────────

def send_group(message: str, group_id: str = None) -> bool:
    try:
        import pywhatkit as pwk
    except ImportError:
        print("  [ERROR] pywhatkit not installed. Run: pip install pywhatkit")
        return False

    gid = group_id or WHATSAPP_GROUP_ID
    if not gid:
        print("  [ERROR] WHATSAPP_GROUP_ID not set in .env")
        print("  Find it: WhatsApp group → Invite link → https://chat.whatsapp.com/<ID>")
        return False

    # schedule 2 minutes from now to give WhatsApp Web time to open
    now       = datetime.datetime.now() + datetime.timedelta(minutes=2)
    send_hour = now.hour
    send_min  = now.minute

    parts = split_message(message, max_len=1000)   # pywhatkit is more sensitive to length
    print(f"  → Sending {len(parts)} message(s) to group {gid} at {send_hour:02d}:{send_min:02d} …")
    print("  WhatsApp Web will open in your browser — keep it logged in.")

    ok = True
    for i, part in enumerate(parts):
        try:
            # wait_time=15: seconds to wait after opening browser before sending
            # tab_close=True: closes the browser tab after sending
            pwk.sendwhatmsg_to_group(
                group_id=gid,
                message=part,
                time_hour=send_hour,
                time_min=send_min,
                wait_time=20,
                tab_close=True,
                close_time=5,
            )
            print(f"    Part {i+1}/{len(parts)} sent.")
        except Exception as e:
            print(f"    [ERROR] Part {i+1}: {e}")
            ok = False

        if i < len(parts) - 1:
            # next part 1 minute later
            nxt = datetime.datetime.now() + datetime.timedelta(minutes=1)
            send_hour, send_min = nxt.hour, nxt.minute
            time.sleep(5)

    return ok


# ── report loader ──────────────────────────────────────────────────────────────

def load_latest_reports() -> list[dict]:
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


# ── public entry point ─────────────────────────────────────────────────────────

def notify(reports: list[dict] = None, mode: str = None,
           to: str = None, group_id: str = None) -> bool:
    """Called from yt_multi_channel.py --notify"""
    if reports is None:
        reports = load_latest_reports()
    if not reports:
        print("  [WARN] No reports to notify about.")
        return False

    active_mode = mode or WHATSAPP_MODE
    date_label  = datetime.date.today().strftime("%d %b %Y")
    message     = build_message(reports, date_label)

    print(f"\n  WhatsApp notification  mode={active_mode}  channels={len(reports)}")

    if active_mode == "group":
        return send_group(message, group_id=group_id)
    else:
        recipients = _parse_recipients(to) if to else None
        return send_individual(message, recipients=recipients)


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Send YouTube analytics to WhatsApp")
    parser.add_argument("--mode",     choices=["individual", "group"],
                        help="Override WHATSAPP_MODE from .env")
    parser.add_argument("--to",       help="Individual recipient(s), comma-separated +91XXXXXXXXXX")
    parser.add_argument("--group-id", help="WhatsApp group ID (override WHATSAPP_GROUP_ID)")
    parser.add_argument("--report",   help="Specific JSON report file")
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
            print("No reports found. Run: python yt_multi_channel.py")
            sys.exit(1)

    success = notify(
        reports,
        mode=args.mode,
        to=args.to,
        group_id=args.group_id,
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
