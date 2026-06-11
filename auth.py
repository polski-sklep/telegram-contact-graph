import os
from dotenv import load_dotenv
from telethon.sync import TelegramClient

load_dotenv()

api_id = int(os.getenv("TG_API_ID"))
api_hash = os.getenv("TG_API_HASH")

with TelegramClient("telegram_session", api_id, api_hash) as client:
    me = client.get_me()
    print(f"Logged in as: {me.first_name} {me.last_name or ''} (@{me.username})")
