# Telegram Contact Graph

Telethon scripts that sign in as your own Telegram account, walk the dialogs Telethon returns, and write one aggregated record per person to `contacts_raw.json`.

The full sweep lives in `extractor.py`. A direct message with a person who is not a bot is enough to create a record. Group and supergroup records are created only when a message matches the interaction rules below. The intended use is to rebuild a personal contact list from your own Telegram history, for example before outreach, deduplication, or CRM enrichment. The program itself only reads Telegram and writes a local JSON file.

## What the sweep does

1. Load `TG_API_ID` and `TG_API_HASH` from the environment (a `.env` file in the working directory is loaded when present).
2. Open the local session file `telegram_session.session` and sign in if that file is missing.
3. Walk dialogs one at a time.
4. Skip your Saved Messages chat (`User.is_self`) and skip broadcast channels (`Channel.broadcast`).
5. For any other user dialog, skip bots, then store that user's profile fields and scan the direct message history.
6. For a basic group (`Chat`) or a non-broadcast channel (a supergroup), scan messages for replies and for mentions that carry a user id.
7. For contacts that still have neither a username nor a first name, call `get_entity` and copy username, name, and `is_bot` when the result is a user.
8. Turn each `shared_groups` set into a sorted list and write `contacts_raw.json` in the working directory. The file is written only after the sweep finishes. A crash before that leaves any previous file unchanged, and a successful run overwrites it.

Progress is printed at the start, every 25 dialogs, and at the end (dialog count and contact count).

## What each contact contains

| Field | How it is filled |
| --- | --- |
| `user_id` | Telegram user id. The JSON object key is that same id as a string, because JSON object keys are strings. |
| `username`, `first_name`, `last_name` | Taken from the direct-message user object. For someone seen only in a group, filled later by `get_entity` when that lookup succeeds. |
| `phone` | Copied from the direct-message user object when Telegram includes it there. Group-only contacts are not given a phone number. The sweep never calls a full-user request. |
| `bio` | Always `null`. The key is created on every record and never assigned. |
| `is_bot` | From the direct-message user object, or from `get_entity` for a group-only contact whose name was missing. Stays `false` when that lookup fails. |
| `dm_message_count` | Number of direct messages with a non-empty text body whose date is on or after the cutoff. Media-only and empty messages are ignored. |
| `dm_messages_sample` | Up to 30 of those text messages, newest first. Each item has `from` (`me` or `them`), `date` (ISO 8601), and `text` truncated to 500 characters. |
| `group_interactions` | Up to 20 matching group messages, in the order they are found (dialogs in Telethon's order, messages newest first inside each chat). Further matches still update `shared_groups` but are not appended. |
| `shared_groups` | Sorted chat titles in which a stored interaction was found. This is not the full set of groups you both belong to. A missing title is stored as `Unknown`. Two chats with the same title collapse to one entry. |

A direct-message contact is stored even when every message is older than the cutoff or has no text. In that case `dm_message_count` is `0` and `dm_messages_sample` is empty.

A group interaction excerpt is the text of the message being scanned, not the message it replied to:

- `you_replied_to_them`: your reply text
- `they_replied_to_you`: their reply text
- `you_mentioned_them`: your message text

Dates on those items are the date of that same message. Excerpts are truncated to 300 characters.

## How a group message is classified

Only messages with a non-empty text body are considered. Scanning of a chat stops at the first message older than the cutoff, which works because Telethon yields messages newest first.

A message can contribute at most one contact:

- You sent it, it replies to someone else, and that reply can be loaded: `you_replied_to_them`.
- Someone else sent it, it replies to you, and that reply can be loaded: `they_replied_to_you`.
- You sent it and it contains a `MessageEntityMentionName` (a mention that carries a user id): `you_mentioned_them`.

If both a reply and one or more `MessageEntityMentionName` entities are present, the last such mention replaces the reply. The reply target is then dropped, and only that one user is recorded for the message. A failed reply lookup is ignored and the scan continues.

Plain `@username` text (`MessageEntityMention`) is not stored. The branch that notices another person's `@mention` reads the slice of text and then discards it. Mentions you type as plain `@username`, without a user-id entity, are not stored either.

Bots are skipped only in direct messages. A bot that matches a group rule is stored like any other user.

If scanning a group raises, the script prints the chat title and the error and moves on. Interactions already appended from that chat stay in the result. Direct-message scans have no such handler: an error there stops the run.

## What is left out

- Broadcast channels.
- Saved Messages.
- Direct messages with bots.
- Messages with no text body.
- Messages strictly older than the cutoff.
- Plain `@username` mentions, in either direction.
- Biography text, and phone numbers for people who appear only in groups.
- Membership of a shared group when no reply or user-id mention was found there.
- Any resume cursor, date window flag, or partial output file.

## Cutoff

The cutoff is a constant, not an environment variable. `extractor.py` and `test_extract_one.py` each define:

```python
CUTOFF = datetime(2021, 12, 31, tzinfo=timezone.utc)
```

That instant is 31 December 2021 at 00:00 UTC. Messages with an earlier timestamp are ignored. Messages from that moment onward are kept. The two copies are independent: change both if the diagnostic script should use the same window as the sweep. There is no other configuration for the window.

## Tech stack

- Python 3. The repository does not pin an interpreter. The scripts use `asyncio.run` and the standard library (`asyncio`, `json`, `os`, `sys`, `datetime`, `collections`).
- [Telethon](https://docs.telethon.dev/) for the Telegram client. No version is pinned.
- [python-dotenv](https://github.com/theskumar/python-dotenv) to load a `.env` file. No version is pinned.

There is no `requirements.txt`, `pyproject.toml`, or lockfile. There is no automated test runner, linter config, or application framework.

## Repository layout

| Path | Role |
| --- | --- |
| `extractor.py` | Full sweep. Writes `contacts_raw.json`. |
| `auth.py` | One-time interactive sign-in. Prints the logged-in name and username. |
| `test_dialogs.py` | Manual check: prints the first 10 dialogs (entity class name and title). |
| `test_extract_one.py` | Manual check of one dialog. See below for how it differs from the sweep. |
| `.env.example` | Names of the two environment variables, with empty values. |
| `.gitignore` | Ignores `.env`, `*.session`, `contacts_raw.json`, `contacts_*.json`, and `extraction.log`. The scripts do not write `extraction.log`. |
| `SECURITY.md` | Vulnerability reporting and what to do if a secret is committed. |
| `LICENSE` | MIT licence. |

All four Python files are standalone scripts. Nothing is packaged as an importable library.

## Prerequisites

- A current Python 3 interpreter, with `venv` and `pip`.
- A Telegram user account. The client logs in as you. It is not a bot token.
- An API id and API hash from [my.telegram.org/auth](https://my.telegram.org/auth), under API development tools.

## Install

```bash
git clone <your-fork-url> telegram-contact-graph
cd telegram-contact-graph
python3 -m venv .venv
source .venv/bin/activate
pip install telethon python-dotenv
```

On Windows, activate the virtual environment with `.venv\Scripts\activate` instead.

## Configuration

Copy the example file and set both variables. Do not commit `.env`.

```bash
cp .env.example .env
```

| Variable | Required | Used as |
| --- | --- | --- |
| `TG_API_ID` | Yes | Passed through `int()`. A missing or non-numeric value raises as soon as the script imports. |
| `TG_API_HASH` | Yes | Passed straight through to `TelegramClient`. |

No other environment variables are read.

`python-dotenv` loads `.env` from the current working directory and does not override variables that are already set. Run the scripts from the directory that contains `.env`, or export the two variables yourself.

The session name in every script is `telegram_session`, so Telethon writes `telegram_session.session` in the working directory. That file is a bearer credential: anyone who has it, together with the API id and hash, can use your account. `.gitignore` ignores `*.session` and `*.session-journal`. Treat the session file like a password and do not commit it.

## Run locally

Sign in once:

```bash
python auth.py
```

The first run uses Telethon's interactive sign-in: it asks for your phone number, the login code Telegram sends, and the two-step verification password when the account has one. Later runs reuse `telegram_session.session`. A successful login prints your first name, last name, and username.

Then:

```bash
# List the first 10 dialogs to confirm the session works.
python test_dialogs.py

# Inspect one dialog. The argument is a case-insensitive substring of the dialog title.
python test_extract_one.py "some chat title"

# Full sweep. Overwrites contacts_raw.json.
python extractor.py
```

`test_extract_one.py` is a separate copy of part of the rules, not a call into `extractor.py`.

- With no argument it searches for the substring `t3rn` (a hard-coded default).
- It uses the first dialog whose name contains the substring.
- For a user dialog it prints a text-message count since the cutoff. It does not skip bots, and it does not print excerpts.
- For a group or supergroup it counts reply interactions only. It does not apply the `MessageEntityMentionName` rule. It prints at most 10 people, with a username or name when `get_entity` succeeds.
- For a broadcast channel it prints a skip message and exits.
- It does not write JSON.

`test_dialogs.py` and `test_extract_one.py` are manual diagnostics. The repository has no unit tests, no pytest suite, and no CI workflow.

## Output schema

```json
{
  "123456789": {
    "user_id": 123456789,
    "username": "alice_handle",
    "first_name": "Alice",
    "last_name": "Smith",
    "phone": "+15551234567",
    "bio": null,
    "is_bot": false,
    "dm_message_count": 47,
    "dm_messages_sample": [
      { "from": "me", "date": "2024-03-15T14:22:00+00:00", "text": "..." },
      { "from": "them", "date": "2024-03-15T14:23:00+00:00", "text": "..." }
    ],
    "group_interactions": [
      {
        "group": "Group Title",
        "via": "you_replied_to_them",
        "date": "2024-02-10T09:11:00+00:00",
        "excerpt": "..."
      }
    ],
    "shared_groups": ["Group A", "Group B"]
  }
}
```

The phone value above is only an illustration. It appears in real output only when the direct-message user object already contains a number. `bio` is always `null` with the current code. `via` is one of `you_replied_to_them`, `they_replied_to_you`, or `you_mentioned_them`.

## Limits and failures

Dialogs are processed one after another. The scripts construct `TelegramClient` with Telethon's defaults: they do not set a flood-wait threshold, a retry policy, or a checkpoint. Any automatic wait on a short flood-wait error is Telethon's own default for the version you installed.

There is no segment mode. Each `extractor.py` run walks every dialog Telethon returns and then replaces `contacts_raw.json`. For a large account that means a long run, and a failure in a direct message means starting again from scratch.

## Privacy

The tool reads only data your own account can already access. It does not bypass Telegram's access controls.

You are responsible for the output. `contacts_raw.json` contains other people's names, usernames, phone numbers where Telegram already shared them with you, and message excerpts. Those people did not agree to have that interaction history copied into a JSON file. Treat the file as sensitive:

- Restrict permissions, for example `chmod 600 contacts_raw.json`.
- Do not commit it. `contacts_raw.json` and `contacts_*.json` are already listed in `.gitignore`.
- Do not upload it in bulk to a third-party language model without deciding whether that disclosure is acceptable.
- Do not use the excerpts as personalisation in cold outreach without considering whether you would want the same done with your own messages.

## Security

`.env` and `*.session` are listed in `.gitignore`. The session file grants access to your account. See `SECURITY.md` for how to report a vulnerability and what to do if a secret is committed.

`SECURITY.md` also mentions an LLM provider, a bot allow-list, and a web app behind Tailscale. None of that code is in this repository. The only network client here is Telethon, talking to Telegram. Nothing in these scripts sends message text to any other service.

## Deployment

Run the scripts on your own machine. This repository has no Dockerfile, Compose file, CI workflow, hosting config, or process manager. `.gitignore` lists `docker-compose.override.yml`, but no Compose file is shipped.

## Licence

MIT. Copyright (c) 2026 Jacob Kowalewski. See `LICENSE`.
