"""Test extraction logic on a single group or DM by name."""
import os
import asyncio
import sys
from datetime import datetime, timezone
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.tl.types import User, Chat, Channel

load_dotenv()
API_ID = int(os.getenv("TG_API_ID"))
API_HASH = os.getenv("TG_API_HASH")
CUTOFF = datetime(2021, 12, 31, tzinfo=timezone.utc)

async def main(query):
    client = TelegramClient("telegram_session", API_ID, API_HASH)
    await client.start()
    me = await client.get_me()
    print(f"My ID: {me.id}\n")

    # find a dialog matching the query
    target = None
    async for dialog in client.iter_dialogs():
        if query.lower() in dialog.name.lower():
            target = dialog
            print(f"Match: [{type(dialog.entity).__name__}] {dialog.name}")
            break

    if not target:
        print(f"No dialog matching '{query}'")
        await client.disconnect()
        return

    entity = target.entity
    interactions = {}

    if isinstance(entity, User):
        # DM
        count = 0
        async for msg in client.iter_messages(entity, limit=None):
            if msg.date < CUTOFF:
                break
            if msg.message:
                count += 1
        print(f"DM: {count} messages since {CUTOFF.date()}")

    elif isinstance(entity, (Chat, Channel)):
        if isinstance(entity, Channel) and entity.broadcast:
            print("Broadcast channel — skipped.")
            await client.disconnect()
            return
        msg_scanned = 0
        async for msg in client.iter_messages(entity, limit=None):
            if msg.date < CUTOFF:
                break
            msg_scanned += 1
            if not msg.message:
                continue

            if msg.sender_id == me.id and msg.reply_to_msg_id:
                try:
                    replied = await msg.get_reply_message()
                    if replied and replied.sender_id and replied.sender_id != me.id:
                        interactions.setdefault(replied.sender_id, []).append("you replied to them")
                except Exception:
                    pass
            elif msg.sender_id != me.id and msg.reply_to_msg_id:
                try:
                    replied = await msg.get_reply_message()
                    if replied and replied.sender_id == me.id:
                        interactions.setdefault(msg.sender_id, []).append("they replied to you")
                except Exception:
                    pass

        print(f"Group: scanned {msg_scanned} messages, found {len(interactions)} interaction contacts")
        for uid, evts in list(interactions.items())[:10]:
            try:
                u = await client.get_entity(uid)
                handle = f"@{u.username}" if u.username else f"{u.first_name or ''} {u.last_name or ''}".strip()
            except Exception:
                handle = f"id={uid}"
            print(f"  {handle}: {len(evts)} interaction(s)")

    await client.disconnect()

if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else "t3rn"
    asyncio.run(main(query))
