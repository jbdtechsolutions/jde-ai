Start the YouTube Analytics dashboard server.

Run from the project root:
```
venv\Scripts\activate && python dashboard/serve.py
```

This opens the dashboard automatically at http://localhost:8765

If the user specifies a port (e.g. "on port 9000"), use `--port 9000`.
If the user says "headless" or "no browser", add `--no-browser`.

The dashboard displays:
- One tab per channel
- Stat cards: subscribers, total views, video count, avg views/video
- Charts: top videos by views, upload activity by year
- Engagement summary across recent videos
- Sortable, searchable video table

Remind the user to run `python yt_multi_channel.py` first if the reports/ folder is empty.
