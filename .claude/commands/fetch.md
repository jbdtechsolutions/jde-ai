Fetch YouTube analytics for all channels in channels.json.

Run the following command from the project root:
```
venv\Scripts\activate && python yt_multi_channel.py
```

If the user specifies a date range like "last 90 days" or "January to March", add the appropriate flags:
- `--days 90` for N days back
- `--start YYYY-MM-DD --end YYYY-MM-DD` for explicit range

If the user says "fetch and notify" or "fetch and send", add `--notify` flag.

After running, report:
- How many channels were fetched
- Any errors or warnings
- Where reports were saved
- Subscriber and view counts for each channel
