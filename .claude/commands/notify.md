Send the latest YouTube analytics summary to WhatsApp.

Run from the project root:
```
venv\Scripts\activate && python notify_whatsapp.py
```

Mode is controlled by WHATSAPP_MODE in .env:
- `group`      → sends to JBDE Admin WhatsApp group via pywhatkit (WhatsApp Web)
- `individual` → sends to TWILIO_WHATSAPP_TO number(s) via Twilio

If the user says "send to group", add `--mode group`.
If the user says "send to my number" or gives a phone number, add `--mode individual --to +91XXXXXXXXXX`.
If the user says "send a specific channel", add `--report reports/<channel>_<date>.json`.

Before running, check that:
1. reports/ directory has at least one JSON report file
2. .env has WHATSAPP_GROUP_ID set (for group mode) or TWILIO_* vars (for individual mode)

After running, confirm which group/number the message was sent to and whether it succeeded.
