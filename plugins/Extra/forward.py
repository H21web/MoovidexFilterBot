import asyncio
import re
import random
import logging
from collections import defaultdict
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ChatType

# === CONFIGURATION ===
api_id = 8281168 # Replace with your API ID
api_hash = '445ff67ec34858448ac184c7479ce917'  # Replace with your API Hash
session_name = 'mvdex'

# Logging setup
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')

# Main forwarding channels (source: destination)
main_channels = {
    -1000000000000: -2000000000000, 
    -3000000000000: -4000000000000,
}

# Keyword-based forwarding
keyword_channels = {
    ("word", "phrase", "expression"): -100000200000,
    ("alphabet",): -1000000200000,
}

compiled_keywords = [
    (re.compile(rf'\b({"|".join(words)})\b', flags=re.IGNORECASE), channel)
    for words, channel in keyword_channels.items()
]

app = Client(session_name, api_id=api_id, api_hash=api_hash)

# For storing grouped (album) messages
group_buffer = defaultdict(list)
group_timers = {}

def extract_text_and_filenames(messages: list[Message]) -> str:
    text_parts = []
    filenames = []

    for msg in messages:
        if msg.text:
            text_parts.append(msg.text)

        if msg.document and msg.document.file_name:
            filenames.append(msg.document.file_name)

    return " ".join(text_parts + filenames)

async def process_and_forward(messages: list[Message], source_id: int):
    dest_id = main_channels.get(source_id)
    if not dest_id:
        return

    # Forward to main channel
    try:
        await app.forward_messages(chat_id=dest_id, from_chat_id=source_id, message_ids=[msg.id for msg in messages])
        logging.info(f"📦 Main forward: {source_id} → {dest_id}")
    except Exception as e:
        logging.error(f"❌ Error forwarding to main channel ({dest_id}): {e}")

    # Keyword-based forwarding
    content = extract_text_and_filenames(messages)
    found_channels = set()

    for regex, channel_id in compiled_keywords:
        if regex.search(content):
            if channel_id not in found_channels:
                try:
                    await app.forward_messages(chat_id=channel_id, from_chat_id=source_id, message_ids=[msg.id for msg in messages])
                    logging.info(f"🔑 Keyword match {regex.pattern} → forwarded to {channel_id}")
                    found_channels.add(channel_id)
                except Exception as e:
                    logging.error(f"❌ Error forwarding to keyword channel ({channel_id}): {e}")

    await asyncio.sleep(random.uniform(3, 5))

async def flush_album(grouped_id, source_id):
    messages = group_buffer.pop(grouped_id, [])
    group_timers.pop(grouped_id, None)
    if messages:
        await process_and_forward(messages, source_id)

@app.on_message(filters.chat(list(main_channels.keys())) & filters.group)
async def message_handler(client, message: Message):
    grouped_id = message.media_group_id
    source_id = message.chat.id

    if grouped_id:
        group_buffer[grouped_id].append(message)

        if group_timers.get(grouped_id):
            group_timers[grouped_id].cancel()

        group_timers[grouped_id] = asyncio.get_event_loop().call_later(
            1.5, lambda: asyncio.create_task(flush_album(grouped_id, source_id))
        )
    else:
        await process_and_forward([message], source_id)

@app.on_message(filters.chat(list(main_channels.keys())) & filters.private)
async def private_handler(client, message: Message):
    await process_and_forward([message], message.chat.id)

async def main():
    await app.start()
    logging.info("✅ Script running")
