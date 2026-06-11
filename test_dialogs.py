"""Quick test: list first 10 dialogs to confirm Telethon is working."""
import os
import asyncio
from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv()
API_ID = int(os.getenv("TG_API_ID"))
API_HASH = os.getenv("TG_API_HASH")

async def main():
    client = TelegramClient("telegram_session", API_ID, API_HASH)
    await client.start()
    print("Connected.\n")
    count = 0
    async for dialog in client.iter_dialogs(limit=10):
        kind = type(dialog.entity).__name__
        print(f"  [{kind}] {dialog.name}")
        count += 1
    print(f"\nListed {count} dialogs.")
    await client.disconnect()

asyncio.run(main())
