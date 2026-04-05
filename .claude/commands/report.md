Show a summary of the latest analytics reports from the reports/ directory.

Read all JSON files in reports/ that match the pattern <channel>_YYYY-MM-DD.json (exclude _videos_, _analytics_, summary files).

For each channel, display:
- Channel name and fetch date
- Subscribers, total views, video count
- Top video (by view count) with views and likes
- Engagement rate across recent videos

Present this as a formatted table or structured summary.

If reports/ is empty or doesn't exist, tell the user to run:
  python yt_multi_channel.py

If the user asks for a specific channel, filter to only that channel's report.
If the user asks for a date range or specific date, filter accordingly.
