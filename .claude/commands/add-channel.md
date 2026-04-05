Add a new YouTube channel to channels.json for tracking.

The user will provide a YouTube channel URL or handle such as:
- https://www.youtube.com/@channelname
- @channelname
- A channel name

Steps:
1. Extract the handle from the URL (the part after @)
2. Read channels.json
3. Check if the channel is already in the list — if yes, tell the user
4. Add a new entry:
   ```json
   {
     "name": "<Display Name>",
     "handle": "@<handle>",
     "channel_id": "",
     "owned": false,
     "notes": "Channel ID auto-resolved from handle on first run"
   }
   ```
5. Save channels.json
6. Tell the user to run `python yt_multi_channel.py` to fetch data for the new channel

If the user says they own the channel, set `"owned": true` and remind them they need client_secrets.json for OAuth analytics.
