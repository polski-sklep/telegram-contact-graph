# Telegram Contact Graph

Scripts that sign in as your own Telegram account, walk the dialogs Telethon returns, and write one aggregated record per user to `contacts_raw.json`.

The sweep is `extractor.py`. A direct message with a person who is not a bot creates a record even when no message falls inside the date window. A group or supergroup creates a record only when a message matches the rules below. The scripts only read Telegram and write that local JSON file, so you can rebuild a contact list from your own history since the cutoff below.

## What the sweep does

1. Load `TG_API_ID` and `TG_API_HASH` (see Configuration).
2. Open a session named `telegram_session`. If `telegram_session.session` is missing, Telethon's default sign-in prompts run.
3. Walk dialogs one at a time.
4. Skip the dialog whose user has `is_self` set (Saved Messages). Skip broadcast channels (`Channel.broadcast`).
5. For any other user dialog, skip bots, then store that user's profile fields and scan the direct-message history.
6. For a basic group (`Chat`) or a non-broadcast channel (a supergroup), scan messages for replies and for mentions that carry a user id.
7. For contacts that still have neither a username nor a first name, call `get_entity` and, when the result is a user, copy username, first name, last name, and `is_bot`.
8. Turn each `shared_groups` set into a sorted list and write `contacts_raw.json` in the working directory.

The file is opened only after the sweep returns, in write mode (`indent=2`). A failure during the sweep leaves an existing file untouched. A failure while writing can leave a partial file. A finished run replaces the previous file.

Progress lines print your user id, "Enumerating dialogs...", a line every 25 dialogs (dialogs processed and contacts so far), the totals, and "Hydrating user profiles...". Per-group scan errors and failed profile lookups are printed as they happen. The last line is the number of contacts written.

## What each contact contains

| Field | How it is filled |
| --- | --- |
| `user_id` | Telegram user id. The JSON object key is that same id as a string, because `json.dump` stringifies non-string keys. |
| `username`, `first_name`, `last_name` | From the direct-message user object. For someone seen only in a group, filled by `get_entity` when both were still empty and the lookup returns a user. |
| `phone` | Copied from the direct-message user object when that object includes it. Group-only contacts do not get a phone number. Hydration does not copy `phone`. |
| `bio` | Always `null`. The key is created on every record and never assigned. |
| `is_bot` | From the direct-message user object, or from `get_entity` for a group-only contact whose username and first name were both missing. Stays `false` when that lookup fails or the result is not a user. Direct-message bots never reach this field: they are skipped before a record is created. |
| `dm_message_count` | Number of direct messages with a non-empty text body on or after the cutoff. Messages with no text are ignored. |
| `dm_messages_sample` | Up to 30 of those text messages, in the order `iter_messages` yields them (Telethon's default is newest first; the scripts do not pass `reverse`). Each item has `from` (`me` or `them`, from `sender_id`), `date` (`isoformat()`), and `text` cut to 500 characters. |
| `group_interactions` | Up to 20 matching group messages, in the order they are found: dialogs in Telethon's dialog order, messages newest first inside each chat. Later matches still update `shared_groups` and are not appended. |
| `shared_groups` | Sorted chat titles in which a stored interaction was found. A missing title is stored as `Unknown`. Two chats with the same title become one entry, because the titles are held in a set. This list is built only from stored interactions. |

A direct-message contact is stored even when every message is older than the cutoff or has no text. Then `dm_message_count` is `0` and `dm_messages_sample` is empty.

A group excerpt is the text of the message being scanned, not the message it replied to:

- `you_replied_to_them`: your reply text
- `they_replied_to_you`: their reply text
- `you_mentioned_them`: your message text

The date on those items is the date of that same message. Excerpts are cut to 300 characters.

## How a group message is classified

Only messages with a non-empty text body are considered. The scan of a chat stops at the first message older than the cutoff. That matches Telethon's default `iter_messages` order (newest first). The scripts do not pass `reverse`. The same stop applies to direct messages.

A message contributes at most one contact:

- You sent it, it has `reply_to_msg_id`, the replied-to message loads, and that sender is someone else: `you_replied_to_them`.
- Someone else sent it, it has `reply_to_msg_id`, the replied-to message loads, and that sender is you: `they_replied_to_you`.
- You sent it and it contains a `MessageEntityMentionName` (a mention that carries a user id): `you_mentioned_them`. The last such entity on the message is the one kept.

On a message you sent, a `MessageEntityMentionName` replaces a reply classification for that message. The reply target is dropped. If the last of those mentions is your own user id, the message is discarded and neither the mention nor the reply is stored.

A failed reply lookup is ignored and the scan continues with the mention check.

Plain `@username` text (`MessageEntityMention`) is not stored. The branch that sees another person's `@mention` slices that text and then discards it. Mentions you type as plain `@username`, without a user-id entity, are not stored either. A `MessageEntityMentionName` on a message you did not send is ignored. If that message is also a reply to you, the reply rule still records the sender.

Bots are skipped only in direct messages. A bot that matches a group rule is stored like any other user.

If scanning a group raises, the script prints `skipped group '<title>': <error>` and moves on. Interactions already appended from that chat stay in the result. Direct-message scans have no such handler. An error there stops the run, and `contacts_raw.json` is not opened.

## Left out

- Broadcast channels.
- Saved Messages (`User.is_self`).
- Direct messages with bots.
- Messages with no text body.
- Messages strictly older than the cutoff.
- Plain `@username` mentions, in either direction.
- `MessageEntityMentionName` entities on messages you did not send.
- Biography text, and phone numbers for people who appear only in groups.
- A group you both belong to when that chat produced no stored reply (either direction) and no user-id mention from you.
- Any resume cursor, date-window flag, or partial output written during the sweep.

## Cutoff

The cutoff is a constant, not an environment variable. The comment above it says "end of 2021". The value is the start of that day. `extractor.py` and `test_extract_one.py` each define:

```python
CUTOFF = datetime(2021, 12, 31, tzinfo=timezone.utc)
```

That instant is 31 December 2021 at 00:00 UTC. A message with an earlier timestamp stops the scan of that chat. A message from that moment onward is eligible. The two copies are independent. Change both if the diagnostic script should use the same window as the sweep.

## Stack

- Python 3.7 or newer. The scripts call `asyncio.run`. The repository does not pin an interpreter. Standard library modules used: `asyncio`, `json`, `os`, `sys`, `datetime`, `collections`.
- [Telethon](https://docs.telethon.dev/) as the Telegram client. No version is pinned. `auth.py` uses `telethon.sync.TelegramClient`. The other three scripts use the async client.
- [python-dotenv](https://github.com/theskumar/python-dotenv) (`load_dotenv`). No version is pinned.

There is no `requirements.txt`, `pyproject.toml`, or lockfile. There is no web framework, database, or second API client. The only outbound client in these scripts is Telethon, talking to Telegram.

## Repository layout

| Path | Role |
| --- | --- |
| `extractor.py` | Full sweep. Writes `contacts_raw.json`. |
| `auth.py` | One-time interactive sign-in. Prints the logged-in name and username. |
| `test_dialogs.py` | Manual check. Prints the first 10 dialogs: entity class name and `dialog.name`. |
| `test_extract_one.py` | Manual check of one dialog. Separate copy of part of the rules. See below. |
| `.env.example` | Names of the two environment variables, with empty values. |
| `.gitignore` | Ignores `.env`, `*.session`, `*.session-journal`, `contacts_raw.json`, `contacts_*.json`, and `extraction.log`. The scripts do not write `extraction.log`. |
| `SECURITY.md` | Vulnerability reporting, and what to do if a secret is committed. See Security below before relying on the rest of that file. |
| `LICENSE` | MIT licence. Copyright (c) 2026 Jacob Kowalewski. |

All four Python files are standalone scripts in the repository root. Nothing is packaged as an importable library.

## Prerequisites

- Python 3.7 or newer, with `venv` and `pip`.
- A Telegram user account. The client logs in as you. It is not a bot token.
- An API id and API hash from [my.telegram.org](https://my.telegram.org/auth), under API development tools. That URL is the one named in `.env.example`.

## Install

```bash
git clone https://github.com/polski-sklep/telegram-contact-graph
cd telegram-contact-graph
python3 -m venv .venv
source .venv/bin/activate
pip install telethon python-dotenv
```

On Windows, activate with `.venv\Scripts\activate`.

## Configuration

Copy the example file and set both variables. `.env` is gitignored.

```bash
cp .env.example .env
```

| Name | Read in | Purpose |
| --- | --- | --- |
| `TG_API_ID` | `auth.py`, `extractor.py`, `test_dialogs.py`, `test_extract_one.py` | Passed through `int()` and given to `TelegramClient` as the API id. A missing or non-numeric value raises as soon as the script loads. |
| `TG_API_HASH` | same four files | Passed through to `TelegramClient` as the API hash. |

No other environment variable is read by these scripts. Each script calls `load_dotenv()` with no path, then `os.getenv`. When you run the file directly, python-dotenv's default `find_dotenv()` starts at that file's directory and walks upward. Variables already set in the environment are left as they are. Put `.env` next to the scripts, or export the two variables yourself.

The session name in every script is the relative path `telegram_session`, so Telethon writes `telegram_session.session` in the current working directory. `.gitignore` ignores `*.session` and `*.session-journal`. `.env.example` says to treat the session file like a password: it is a bearer credential for the account. Do not commit it.

## Run locally

From the repository root, with the virtual environment active:

```bash
python auth.py
```

`auth.py` opens `TelegramClient` as a context manager, which calls Telethon's `start()`. The first run uses Telethon's default prompts: phone number, the login code Telegram sends, and the two-step verification password when the account has one. Later runs reuse `telegram_session.session` when that file is in the working directory. A successful login prints `Logged in as: <first name> <last name> (@<username>)`. Last name is omitted when it is missing. Username is interpolated as-is, so a missing username shows `(@None)`.

`extractor.py`, `test_dialogs.py`, and `test_extract_one.py` also call `start()`. They prompt the same way when the session file is missing.

```bash
python test_dialogs.py
python test_extract_one.py "some chat title"
python extractor.py
```

`test_dialogs.py` lists up to 10 dialogs and disconnects. It writes nothing.

`test_extract_one.py` does not import `extractor.py`.

- With no argument it searches for the substring `t3rn`. That default is a literal in the script. The repository does not say which chat it refers to.
- It uses the first dialog whose name contains the substring, case-insensitive, and prints the entity class and dialog name.
- For a user dialog it prints a text-message count since the cutoff. It does not skip bots, and it does not print excerpts.
- For a group or supergroup it counts reply interactions only. It does not apply the `MessageEntityMentionName` rule. It prints at most 10 people, with `@username` or a name when `get_entity` succeeds, otherwise `id=<id>`.
- For a broadcast channel it prints `Broadcast channel — skipped.` and exits.
- It writes no JSON.

There is no unit test, pytest suite, or CI workflow. `test_dialogs.py` and `test_extract_one.py` are manual checks. They need the same credentials and a session.

## Output shape

```json
{
  "123456789": {
    "user_id": 123456789,
    "username": "alice_handle",
    "first_name": "Alice",
    "last_name": "Smith",
    "phone": null,
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

Names in that sample are placeholders. `phone` is a string only when the direct-message user object already contains a number; otherwise it stays `null`. `bio` stays `null`. `via` is one of `you_replied_to_them`, `they_replied_to_you`, or `you_mentioned_them`.

## Limits

Dialogs are processed one after another. The scripts construct `TelegramClient` with no flood-wait, retry, or timeout arguments, so those stay at the defaults of the installed Telethon. There is no checkpoint and no segment mode. Each `extractor.py` run walks every dialog and then replaces `contacts_raw.json`. An exception in a direct message ends the run before that write.

## Privacy

The tool reads data your own account can already access. It does not bypass Telegram's access controls.

`contacts_raw.json` contains other people's names, usernames, phone numbers where Telegram already included them on the user object, and message excerpts. Treat the file as sensitive:

- Restrict permissions, for example `chmod 600 contacts_raw.json`.
- Do not commit it. `contacts_raw.json` and `contacts_*.json` are listed in `.gitignore`.
- Do not upload it in bulk to a third-party language model without deciding whether that disclosure is acceptable.
- Do not use the excerpts as personalisation in cold outreach without considering whether you would want the same done with your own messages.

## Security

`.env` and `*.session` are listed in `.gitignore`. See `SECURITY.md` for how it asks you to report a vulnerability and what to do if a secret is committed.

`SECURITY.md` also mentions an LLM provider (Anthropic), a bot allow-list of Telegram user ids, and a web app behind Tailscale. None of that is in this repository. These scripts do not send message text anywhere except to Telegram through Telethon.

## Deployment

There is no Dockerfile, Compose file, CI workflow, hosting config, or process manager. `.gitignore` lists `docker-compose.override.yml`, and no Compose file is in the tree. Run the scripts on your own machine.

## Licence

MIT. Copyright (c) 2026 Jacob Kowalewski. See `LICENSE`.
