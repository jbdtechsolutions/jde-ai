import os
import json
import datetime
import argparse
import sys

# Try importing Google client libraries and provide a clear message if they're missing.
try:
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError as e:
    print("Missing required Google libraries:", e)
    print("Install them with:")
    print("  pip install --upgrade google-auth google-auth-oauthlib google-api-python-client")
    sys.exit(1)

"""
connect-yt.py

Minimal example to authenticate with YouTube (OAuth2) and fetch channel analytics
Requires:
    pip install --upgrade google-auth google-auth-oauthlib google-api-python-client

Place your OAuth client JSON as `client_secrets.json` next to this script.
"""



# Files & scopes
CLIENT_SECRETS_FILE = "client_secrets.json"
TOKEN_FILE = "token.json"
SCOPES = [
        "https://www.googleapis.com/auth/yt-analytics.readonly",
        "https://www.googleapis.com/auth/youtube.readonly",
]


def get_credentials():
        creds = None
        if os.path.exists(TOKEN_FILE):
                creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

        if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                with open(TOKEN_FILE, "w") as f:
                        f.write(creds.to_json())

        if not creds or not creds.valid:
                flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
                creds = flow.run_local_server(port=0)
                with open(TOKEN_FILE, "w") as f:
                        f.write(creds.to_json())

        return creds


def fetch_channel_info(youtube):
        res = youtube.channels().list(part="id,snippet,statistics", mine=True).execute()
        items = res.get("items", [])
        if not items:
                return None
        return items[0]


def fetch_analytics(analytics, start_date, end_date, metrics, dimensions="day"):
        # Use channel==MINE (authorized user's channel)
        return analytics.reports().query(
                ids="channel==MINE",
                startDate=start_date,
                endDate=end_date,
                metrics=metrics,
                dimensions=dimensions,
        ).execute()


def iso_date(days_ago):
        d = datetime.date.today() - datetime.timedelta(days=days_ago)
        return d.isoformat()


def main():
        parser = argparse.ArgumentParser(description="Fetch YouTube channel analytics (basic example).")
        parser.add_argument("--start-date", help="YYYY-MM-DD start date", default=iso_date(30))
        parser.add_argument("--end-date", help="YYYY-MM-DD end date", default=iso_date(0))
        parser.add_argument(
                "--metrics",
                help="Comma-separated metrics (see YouTube Analytics API docs)",
                default="views,estimatedMinutesWatched,averageViewDuration,subscribersGained",
        )
        parser.add_argument("--dimensions", help="Dimensions (optional)", default="day")
        args = parser.parse_args()

        creds = get_credentials()
        youtube = build("youtube", "v3", credentials=creds)
        analytics = build("youtubeAnalytics", "v2", credentials=creds)

        try:
                channel = fetch_channel_info(youtube)
                if channel:
                        title = channel["snippet"].get("title")
                        channel_id = channel.get("id")
                        print(f"Channel: {title} (id={channel_id})")
                else:
                        print("No channel found for the authenticated user.")

                report = fetch_analytics(
                        analytics,
                        start_date=args.start_date,
                        end_date=args.end_date,
                        metrics=args.metrics,
                        dimensions=args.dimensions,
                )

                headers = [h.get("name") for h in report.get("columnHeaders", [])]
                rows = report.get("rows", [])

                print("\nReport headers:")
                print(headers)
                print("\nRows (first 10):")
                for r in rows[:10]:
                        print(r)

                # Save raw report to file for later inspection
                out_file = "yt_analytics_report.json"
                with open(out_file, "w", encoding="utf-8") as f:
                        json.dump(report, f, indent=2, ensure_ascii=False)
                print(f"\nFull report saved to {out_file}")

        except HttpError as e:
                print("API error:", e)


if __name__ == "__main__":
        main()