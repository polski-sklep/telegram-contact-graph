# Telegram Contact Graph

Telethon-based scraper that walks every Telegram dialog you have access to, identifies every user you have directly interacted with (DM, reply, mention) since a configurable cutoff date, and writes an aggregated contact record per user to `contacts_raw.json`.

Intended use: rebuild your personal contact graph from years of Telegram activity for outreach, dedup, or CRM enrichment.

## What it captures, per contact

- Telegram `user_id`, `username`, `first_name`, `last_name`, `phone` (where shared), `bio`, `is_bot`
- DM message count and up to 30 recent excerpts (500-char truncation), annotated with sender (me vs them)
- Group interactions (up to 20 per contact, 300-char truncation): `you_replied_to_them`, `they_replied_to_you`, `you_mentioned_them`
- Shared groups (deduplicated set)

It only counts *interactions* in groups — replies in either direction and `MessageEntityMentionName` mentions from you. Plain `@username` text mentions from others are skipped to avoid false positives.

## What it does not capture

- Broadcast channels (one-way, no interaction signal)
- DMs with bots (filtered by `is_bot`)
- Messages older than the cutoff (`CUTOFF` constant, default end of 2021)

## Setup

### 1. Prerequisites

- Python 3.11+
- A Telegram account (you authenticate as yourself, not as a bot)
- API ID and hash from <https://my.telegram.org/auth> → API development tools

### 2. Install

```bash
git clone <your-fork-url> telegram-contact-graph
cd telegram-contact-graph
python3 -m venv .venv
source .venv/bin/activate
pip install telethon python-dotenv
```

### 3. Configure

```bash
cp .env.example .env
# Fill in:
#   TG_API_ID
#   TG_API_HASH
```

### 4. One-time login

```bash
python auth.py
```

This prompts for the SMS code Telegram sends to your registered phone, then writes a `telegram_session.session` file. Treat this file like a password — it is a bearer credential that grants full read access to your account. It is `.gitignore`'d by default.

### 5. Run

```bash
# Sanity check: list the first 10 dialogs to confirm Telethon is working.
python test_dialogs.py

# Diagnostic: test the interaction-detection rules against one dialog by name.
python test_extract_one.py <substring of dialog name>

# Full sweep: writes contacts_raw.json
python extractor.py
```

## Output schema

```json
{
  "<user_id>": {
    "user_id": 123456789,
    "username": "alice_handle",
    "first_name": "Alice",
    "last_name": "Smith",
    "phone": "+15551234567",
    "bio": null,
    "is_bot": false,
    "dm_message_count": 47,
    "dm_messages_sample": [
      { "from": "me",   "date": "2024-03-15T14:22:00+00:00", "text": "..." },
      { "from": "them", "date": "2024-03-15T14:23:00+00:00", "text": "..." }
    ],
    "group_interactions": [
      { "group": "Group Title", "via": "you_replied_to_them",
        "date": "2024-02-10T09:11:00+00:00", "excerpt": "..." }
    ],
    "shared_groups": ["Group A", "Group B"]
  }
}
```

## Rate limits

The script iterates dialogs sequentially. Telegram rate-limits per account; concurrent scans risk a FloodWait. There is no built-in retry logic — on a FloodWait the script raises and stops. For large accounts (hundreds of dialogs), consider running in segments.

## Privacy and compliance

This tool reads only data your own account already has access to. It does not bypass any access controls.

**You are responsible for how you handle the output.** `contacts_raw.json` contains other users' names, bios, phone numbers (where Telegram shared them with you), and message excerpts. They did not consent to having their interaction footprint extracted into a JSON file. Treat the output as sensitive:

- Restrict file permissions (`chmod 600 contacts_raw.json`)
- Do not commit it (already `.gitignore`'d)
- Do not upload it to a third-party LLM in bulk without thinking through the implications
- Do not use the message excerpts as personalisation hooks in cold outreach without considering whether you would want the equivalent done to you

## Security

`.env` and `*.session` files are in `.gitignore`. The session file is a bearer credential — protect it like a password. See `SECURITY.md`.

## Licence

MIT. See `LICENSE`.
