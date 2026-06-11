"""
Extracts contacts you have directly interacted with across DMs and groups.
Interaction = you sent them a message, they sent you one, or you @mentioned each other.
"""
import os
import asyncio
from datetime import datetime, timezone
from collections import defaultdict
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.tl.types import User, Chat, Channel, MessageEntityMention, MessageEntityMentionName

load_dotenv()
API_ID = int(os.getenv("TG_API_ID"))
API_HASH = os.getenv("TG_API_HASH")
SESSION = "telegram_session"

# Cutoff: end of 2021
CUTOFF = datetime(2021, 12, 31, tzinfo=timezone.utc)


async def get_my_id(client):
    me = await client.get_me()
    return me.id


async def extract_contacts():
    """
    Returns a dict keyed by user_id containing aggregated contact data.
    """
    client = TelegramClient(SESSION, API_ID, API_HASH)
    await client.start()
    my_id = await get_my_id(client)

    # contact_id -> aggregated record
    contacts = defaultdict(lambda: {
        "user_id": None,
        "username": None,
        "first_name": None,
        "last_name": None,
        "phone": None,
        "bio": None,
        "is_bot": False,
        "dm_message_count": 0,
        "dm_messages_sample": [],   # most recent N messages in DM
        "group_interactions": [],   # list of {group_name, message_excerpt, date}
        "shared_groups": set(),
    })

    print(f"My user ID: {my_id}")
    print("Enumerating dialogs...")

    dialog_count = 0
    async for dialog in client.iter_dialogs():
        dialog_count += 1
        entity = dialog.entity

        # DM with a user
        if isinstance(entity, User) and not entity.is_self:
            await process_dm(client, entity, contacts, my_id)

        # Group or supergroup (skip channels — broadcast only, no real interaction)
        elif isinstance(entity, (Chat, Channel)):
            if isinstance(entity, Channel) and entity.broadcast:
                continue  # broadcast channel, skip
            await process_group(client, entity, contacts, my_id)

        if dialog_count % 25 == 0:
            print(f"  processed {dialog_count} dialogs, {len(contacts)} contacts so far")

    print(f"Total dialogs: {dialog_count}")
    print(f"Total interaction contacts: {len(contacts)}")

    # Hydrate user details (bio, etc.) for each contact
    print("Hydrating user profiles...")
    hydrated = await hydrate_contacts(client, contacts)

    await client.disconnect()
    return hydrated


async def process_dm(client, user, contacts, my_id):
    """For a DM, count messages and grab a sample."""
    if user.is_bot:
        return  # skip bots in DMs

    record = contacts[user.id]
    record["user_id"] = user.id
    record["username"] = user.username
    record["first_name"] = user.first_name
    record["last_name"] = user.last_name
    record["phone"] = user.phone
    record["is_bot"] = user.is_bot

    sample = []
    count = 0
    async for msg in client.iter_messages(user, limit=None):
        if msg.date < CUTOFF:
            break
        if not msg.message:
            continue
        count += 1
        if len(sample) < 30:
            sender = "me" if msg.sender_id == my_id else "them"
            sample.append({
                "from": sender,
                "date": msg.date.isoformat(),
                "text": msg.message[:500],
            })
    record["dm_message_count"] = count
    record["dm_messages_sample"] = sample


async def process_group(client, group, contacts, my_id):
    """For a group, find users who interacted with you (mentions or direct replies)."""
    group_name = getattr(group, "title", "Unknown")

    try:
        async for msg in client.iter_messages(group, limit=None):
            if msg.date < CUTOFF:
                break
            if not msg.message:
                continue

            interacted_user_id = None
            interacted_via = None

            # Case 1: you sent a message that replied to someone
            if msg.sender_id == my_id and msg.reply_to_msg_id:
                try:
                    replied_to = await msg.get_reply_message()
                    if replied_to and replied_to.sender_id and replied_to.sender_id != my_id:
                        interacted_user_id = replied_to.sender_id
                        interacted_via = "you_replied_to_them"
                except Exception:
                    pass

            # Case 2: someone replied to you
            elif msg.sender_id != my_id and msg.reply_to_msg_id:
                try:
                    replied_to = await msg.get_reply_message()
                    if replied_to and replied_to.sender_id == my_id:
                        interacted_user_id = msg.sender_id
                        interacted_via = "they_replied_to_you"
                except Exception:
                    pass

            # Case 3: mentions
            if msg.entities:
                for ent in msg.entities:
                    # you mentioned someone
                    if msg.sender_id == my_id and isinstance(ent, MessageEntityMentionName):
                        interacted_user_id = ent.user_id
                        interacted_via = "you_mentioned_them"
                    # someone mentioned you (by @username)
                    elif msg.sender_id != my_id and isinstance(ent, MessageEntityMention):
                        mentioned_text = msg.message[ent.offset:ent.offset+ent.length]
                        # We can only confirm via username later; for now record sender as interaction proxy
                        # Skip generic @ mentions to avoid false positives

            if interacted_user_id and interacted_user_id != my_id:
                record = contacts[interacted_user_id]
                record["user_id"] = interacted_user_id
                record["shared_groups"].add(group_name)
                if len(record["group_interactions"]) < 20:
                    record["group_interactions"].append({
                        "group": group_name,
                        "via": interacted_via,
                        "date": msg.date.isoformat(),
                        "excerpt": msg.message[:300],
                    })
    except Exception as e:
        print(f"  skipped group '{group_name}': {e}")


async def hydrate_contacts(client, contacts):
    """Fill in username/first_name/bio for contacts only seen in groups."""
    out = {}
    for uid, record in contacts.items():
        if not record["username"] and not record["first_name"]:
            try:
                full = await client.get_entity(uid)
                if isinstance(full, User):
                    record["user_id"] = full.id
                    record["username"] = full.username
                    record["first_name"] = full.first_name
                    record["last_name"] = full.last_name
                    record["is_bot"] = full.is_bot
            except Exception as e:
                print(f"  could not hydrate {uid}: {e}")

        # convert set to list for JSON serialization
        record["shared_groups"] = sorted(list(record["shared_groups"]))
        out[uid] = record
    return out


if __name__ == "__main__":
    import json
    contacts = asyncio.run(extract_contacts())
    # write to disk for inspection
    with open("contacts_raw.json", "w") as f:
        json.dump(contacts, f, indent=2, default=str)
    print(f"\nWrote {len(contacts)} contacts to contacts_raw.json")
