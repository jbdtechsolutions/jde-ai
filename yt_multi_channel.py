"""
yt_multi_channel.py
--------------------
Fetch YouTube analytics for multiple channels.

  Public stats (any channel)  — uses YOUTUBE_API_KEY in .env
  Detailed analytics (owned channels) — uses OAuth2 (client_secrets.json)

Usage:
    python yt_multi_channel.py                        # last 30 days, all channels
    python yt_multi_channel.py --days 90              # last 90 days
    python yt_multi_channel.py --start 2025-01-01 --end 2025-03-31
    python yt_multi_channel.py --channels channels.json

Output:
    reports/  ← JSON + CSV files per channel + combined summary
"""

import os
import sys
import json
import csv
import datetime
import argparse
import pathlib

from dotenv import load_dotenv

load_dotenv()

# ── optional Google libs ──────────────────────────────────────────────────────
try:
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
except ImportError as e:
    print("Missing required libraries:", e)
    print("Run:  pip install -r requirements.txt")
    sys.exit(1)

# ── constants ─────────────────────────────────────────────────────────────────
SCOPES = [
    "https://www.googleapis.com/auth/yt-analytics.readonly",
    "https://www.googleapis.com/auth/youtube.readonly",
]

PUBLIC_STATS_PARTS = "id,snippet,statistics,brandingSettings"

ANALYTICS_METRICS = (
    "views,estimatedMinutesWatched,averageViewDuration,"
    "averageViewPercentage,subscribersGained,subscribersLost,"
    "likes,dislikes,comments,shares"
)

REPORTS_DIR = pathlib.Path("reports")

# ── helpers ───────────────────────────────────────────────────────────────────

def iso_date(days_ago: int) -> str:
    return (datetime.date.today() - datetime.timedelta(days=days_ago)).isoformat()


def ensure_reports_dir():
    REPORTS_DIR.mkdir(exist_ok=True)


# ── auth ──────────────────────────────────────────────────────────────────────

def get_oauth_credentials(client_secrets_file: str, token_file: str) -> Credentials:
    """Get (or refresh) OAuth2 credentials, prompting browser login if needed."""
    creds = None
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        pathlib.Path(token_file).write_text(creds.to_json())
        return creds

    if not creds or not creds.valid:
        if not os.path.exists(client_secrets_file):
            raise FileNotFoundError(
                f"OAuth secrets file not found: {client_secrets_file}\n"
                "Download it from Google Cloud Console → OAuth 2.0 Clients → Desktop app."
            )
        flow = InstalledAppFlow.from_client_secrets_file(client_secrets_file, SCOPES)
        creds = flow.run_local_server(port=0)
        pathlib.Path(token_file).write_text(creds.to_json())

    return creds


def build_public_client(api_key: str):
    """YouTube Data API v3 client using API key (public data only)."""
    return build("youtube", "v3", developerKey=api_key)


def build_oauth_clients(client_secrets_file: str, token_file: str):
    """YouTube Data API + Analytics clients using OAuth (owned channel data)."""
    creds = get_oauth_credentials(client_secrets_file, token_file)
    yt = build("youtube", "v3", credentials=creds)
    analytics = build("youtubeAnalytics", "v2", credentials=creds)
    return yt, analytics


# ── channel resolution ────────────────────────────────────────────────────────

def resolve_channel_id(yt_client, channel_entry: dict) -> str | None:
    """
    Return the channel ID from:
      - channel_entry["channel_id"]  (already set)
      - channel_entry["handle"]      (@handle → forHandle lookup)
    Updates channel_entry["channel_id"] in place so the caller can save it.
    """
    if channel_entry.get("channel_id"):
        return channel_entry["channel_id"]

    handle = channel_entry.get("handle", "").lstrip("@")
    if not handle:
        print(f"  [WARN] No channel_id or handle for {channel_entry.get('name')}")
        return None

    try:
        resp = yt_client.channels().list(
            part="id,snippet",
            forHandle=handle,
        ).execute()
        items = resp.get("items", [])
        if items:
            cid = items[0]["id"]
            channel_entry["channel_id"] = cid  # cache for next run
            return cid
        # fallback: search
        resp = yt_client.search().list(
            part="snippet",
            q=handle,
            type="channel",
            maxResults=1,
        ).execute()
        items = resp.get("items", [])
        if items:
            cid = items[0]["snippet"]["channelId"]
            channel_entry["channel_id"] = cid
            return cid
    except HttpError as e:
        print(f"  [ERROR] Resolving handle @{handle}: {e}")

    return None


# ── public stats ──────────────────────────────────────────────────────────────

def fetch_public_stats(yt_client, channel_id: str) -> dict:
    """Fetch publicly available channel statistics."""
    resp = yt_client.channels().list(
        part=PUBLIC_STATS_PARTS,
        id=channel_id,
    ).execute()
    items = resp.get("items", [])
    if not items:
        return {}

    item = items[0]
    snippet = item.get("snippet", {})
    stats = item.get("statistics", {})
    branding = item.get("brandingSettings", {}).get("channel", {})

    return {
        "channel_id": channel_id,
        "title": snippet.get("title"),
        "description": snippet.get("description", "")[:200],
        "custom_url": snippet.get("customUrl"),
        "country": snippet.get("country"),
        "published_at": snippet.get("publishedAt"),
        "keywords": branding.get("keywords"),
        "view_count": int(stats.get("viewCount", 0)),
        "subscriber_count": int(stats.get("subscriberCount", 0)),
        "hidden_subscriber_count": stats.get("hiddenSubscriberCount", False),
        "video_count": int(stats.get("videoCount", 0)),
        "fetched_at": datetime.datetime.utcnow().isoformat() + "Z",
    }


def fetch_recent_videos(yt_client, channel_id: str, max_results: int = 10) -> list[dict]:
    """Fetch the most recent uploads with their public stats."""
    # find the uploads playlist
    resp = yt_client.channels().list(part="contentDetails", id=channel_id).execute()
    items = resp.get("items", [])
    if not items:
        return []

    uploads_playlist = (
        items[0]
        .get("contentDetails", {})
        .get("relatedPlaylists", {})
        .get("uploads")
    )
    if not uploads_playlist:
        return []

    # list playlist items
    pl_resp = yt_client.playlistItems().list(
        part="snippet",
        playlistId=uploads_playlist,
        maxResults=max_results,
    ).execute()

    video_ids = [
        item["snippet"]["resourceId"]["videoId"]
        for item in pl_resp.get("items", [])
    ]
    if not video_ids:
        return []

    # fetch video stats
    vid_resp = yt_client.videos().list(
        part="id,snippet,statistics",
        id=",".join(video_ids),
    ).execute()

    videos = []
    for v in vid_resp.get("items", []):
        s = v.get("statistics", {})
        videos.append({
            "video_id": v["id"],
            "title": v["snippet"].get("title"),
            "published_at": v["snippet"].get("publishedAt"),
            "view_count": int(s.get("viewCount", 0)),
            "like_count": int(s.get("likeCount", 0)),
            "comment_count": int(s.get("commentCount", 0)),
            "url": f"https://www.youtube.com/watch?v={v['id']}",
        })

    return videos


# ── analytics (owned channels) ────────────────────────────────────────────────

def fetch_analytics_report(analytics_client, channel_id: str,
                            start_date: str, end_date: str,
                            metrics: str = ANALYTICS_METRICS,
                            dimensions: str = "day") -> dict:
    """Fetch time-series analytics for an owned channel."""
    resp = analytics_client.reports().query(
        ids=f"channel=={channel_id}",
        startDate=start_date,
        endDate=end_date,
        metrics=metrics,
        dimensions=dimensions,
        sort=dimensions,
    ).execute()

    headers = [h["name"] for h in resp.get("columnHeaders", [])]
    rows = resp.get("rows", [])

    return {
        "channel_id": channel_id,
        "start_date": start_date,
        "end_date": end_date,
        "dimensions": dimensions,
        "metrics": metrics.split(","),
        "headers": headers,
        "rows": rows,
        "row_count": len(rows),
    }


# ── export ────────────────────────────────────────────────────────────────────

def _unique_path(path: pathlib.Path) -> pathlib.Path:
    """If path is locked/exists, append _2, _3 … until a writable name is found."""
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    parent = path.parent
    for i in range(2, 100):
        candidate = parent / f"{stem}_{i}{suffix}"
        if not candidate.exists():
            return candidate
        # also try writing to detect a locked-but-existing file
    return parent / f"{stem}_{datetime.datetime.now().strftime('%H%M%S')}{suffix}"


def save_channel_report(name: str, public_stats: dict, videos: list,
                         analytics: dict | None):
    """Save JSON + CSV reports for a single channel."""
    safe_name = name.lower().replace(" ", "_").replace("/", "-")
    timestamp = datetime.date.today().isoformat()

    report = {
        "channel": name,
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "public_stats": public_stats,
        "recent_videos": videos,
        "analytics": analytics,
    }

    # JSON
    json_path = REPORTS_DIR / f"{safe_name}_{timestamp}.json"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"    Saved JSON → {json_path}")

    # CSV (recent videos)
    if videos:
        csv_path = _unique_path(REPORTS_DIR / f"{safe_name}_videos_{timestamp}.csv")
        try:
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=videos[0].keys())
                writer.writeheader()
                writer.writerows(videos)
            print(f"    Saved CSV  → {csv_path}")
        except PermissionError:
            print(f"    [WARN] CSV locked (close it in Excel?): {csv_path}")

    # CSV (analytics time-series if available)
    if analytics and analytics.get("rows"):
        an_csv_path = _unique_path(REPORTS_DIR / f"{safe_name}_analytics_{timestamp}.csv")
        try:
            with open(an_csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(analytics["headers"])
                writer.writerows(analytics["rows"])
            print(f"    Saved CSV  → {an_csv_path}")
        except PermissionError:
            print(f"    [WARN] CSV locked (close it in Excel?): {an_csv_path}")

    return report


def save_summary(all_reports: list[dict]):
    """Save a combined summary CSV of all channels' public stats."""
    timestamp = datetime.date.today().isoformat()
    summary_path = REPORTS_DIR / f"summary_{timestamp}.csv"

    fieldnames = [
        "channel", "title", "subscriber_count", "view_count",
        "video_count", "country", "custom_url", "published_at",
    ]

    summary_path = _unique_path(summary_path)
    try:
        with open(summary_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for r in all_reports:
                row = {"channel": r["channel"], **r.get("public_stats", {})}
                writer.writerow({k: row.get(k, "") for k in fieldnames})
        print(f"\nSummary CSV -> {summary_path}")
    except PermissionError:
        print(f"\n[WARN] Summary CSV locked (close it in Excel?): {summary_path}")


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Fetch YouTube analytics for multiple channels."
    )
    parser.add_argument(
        "--channels", default="channels.json",
        help="Path to channels config JSON (default: channels.json)"
    )
    parser.add_argument("--start", help="Start date YYYY-MM-DD")
    parser.add_argument("--end",   help="End date YYYY-MM-DD")
    parser.add_argument(
        "--days", type=int, default=30,
        help="Days back from today (used if --start/--end not provided)"
    )
    parser.add_argument(
        "--videos", type=int, default=10,
        help="Number of recent videos to fetch per channel (default: 10)"
    )
    parser.add_argument(
        "--notify", action="store_true",
        help="Send a WhatsApp summary after fetching (requires Twilio config in .env)"
    )
    parser.add_argument(
        "--notify-to",
        help="Override recipient WhatsApp number e.g. +919876543210"
    )
    args = parser.parse_args()

    start_date = args.start or iso_date(args.days)
    end_date   = args.end   or iso_date(0)

    # Load channel config
    config_path = pathlib.Path(args.channels)
    if not config_path.exists():
        print(f"Channel config not found: {config_path}")
        sys.exit(1)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    channels = config.get("channels", [])
    if not channels:
        print("No channels defined in config.")
        sys.exit(1)

    # API key (required for public data)
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        print("ERROR: YOUTUBE_API_KEY not set. Copy .env.example → .env and add your key.")
        sys.exit(1)

    # OAuth (optional — only for owned channels)
    client_secrets_file = os.getenv("CLIENT_SECRETS_FILE", "client_secrets.json")
    token_file          = os.getenv("TOKEN_FILE", "token.json")
    oauth_clients       = None  # built lazily on first owned channel

    ensure_reports_dir()
    yt_public = build_public_client(api_key)

    print(f"\nFetching data for {len(channels)} channel(s)  [{start_date} → {end_date}]\n")

    all_reports = []

    for ch in channels:
        name = ch.get("name", "Unknown")
        owned = ch.get("owned", False)
        print(f"{'─'*55}")
        print(f"Channel : {name}  ({'owned' if owned else 'public'})")

        # Resolve channel ID
        channel_id = resolve_channel_id(yt_public, ch)
        if not channel_id:
            print(f"  [SKIP] Could not resolve channel ID for {name}")
            continue
        print(f"ID      : {channel_id}")

        # Public stats
        print("  → Fetching public stats …")
        try:
            public_stats = fetch_public_stats(yt_public, channel_id)
            sub_count = public_stats.get("subscriber_count", "hidden")
            view_count = public_stats.get("view_count", 0)
            print(f"     Subscribers : {sub_count:,}" if isinstance(sub_count, int) else f"     Subscribers : {sub_count}")
            print(f"     Total views : {view_count:,}")
            print(f"     Videos      : {public_stats.get('video_count', 0):,}")
        except HttpError as e:
            print(f"  [ERROR] Public stats: {e}")
            public_stats = {}

        # Recent videos
        print(f"  → Fetching {args.videos} recent videos …")
        try:
            videos = fetch_recent_videos(yt_public, channel_id, max_results=args.videos)
            print(f"     Found {len(videos)} video(s)")
        except HttpError as e:
            print(f"  [ERROR] Recent videos: {e}")
            videos = []

        # Detailed analytics (owned only)
        analytics_data = None
        if owned:
            print("  → Fetching analytics (OAuth) …")
            try:
                if oauth_clients is None:
                    print("     Launching OAuth browser login …")
                    oauth_clients = build_oauth_clients(client_secrets_file, token_file)
                _, analytics_client = oauth_clients
                analytics_data = fetch_analytics_report(
                    analytics_client, channel_id, start_date, end_date
                )
                print(f"     Analytics rows: {analytics_data['row_count']}")
            except FileNotFoundError as e:
                print(f"  [WARN] {e}")
            except HttpError as e:
                print(f"  [ERROR] Analytics: {e}")

        # Save reports
        print("  → Saving reports …")
        report = save_channel_report(name, public_stats, videos, analytics_data)
        all_reports.append(report)

    # Save summary across all channels
    if all_reports:
        save_summary(all_reports)

    # Persist resolved channel IDs back to config
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\nDone. Channel IDs cached in channels.json for future runs.")

    # WhatsApp notification
    if args.notify:
        try:
            from notify_whatsapp import notify as wa_notify
            to = f"whatsapp:{args.notify_to}" if args.notify_to else None
            wa_notify(all_reports, to=to)
        except ImportError:
            print("[WARN] notify_whatsapp.py not found or twilio not installed.")


if __name__ == "__main__":
    main()
