import asyncio
import re
import random
import logging
from collections import defaultdict
from pyrogram import Client, filters
from pyrogram.types import Message

# === CONFIGURATION ===
api_id = 8281168  # Replace with your API ID
api_hash = '445ff67ec34858448ac184c7479ce917'  # Replace with your API Hash
session_name = 'mvdex'  # For user session. If using bot, use bot_token instead.

# Logging setup
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')

# Main forwarding channels (source: destination)
main_channels = {
    -1002570431865: -1002540224499,
    -1001852694684: -1002540224499,
}

# Keyword-based forwarding (keywords tuple → target channel)
keyword_channels = {
    ("word", "phrase", "expression"): -100000200000,
    ("alphabet",): -1000000200000,
}

# Compile keyword regexes
compiled_keywords = [
    (re.compile(rf'\b({"|".join(re.escape(word) for word in words)})\b', flags=re.IGNORECASE), channel)
    for words, channel in keyword_channels.items()
]

# Initialize the client
app = Client(session_name, api_id=api_id, api_hash=api_hash)

# Buffer and timer tracking for grouped messages
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

    try:
        await app.forward_messages(
            chat_id=dest_id,
            from_chat_id=source_id,
            message_ids=[msg.id for msg in messages]
        )
        logging.info(f"📦 Main forward: {source_id} → {dest_id}")
    except Exception as e:
        logging.error(f"❌ Error forwarding to main channel ({dest_id}): {e}")

    # Keyword-based forwarding
    content = extract_text_and_filenames(messages)
    found_channels = set()

    for regex, channel_id in compiled_keywords:
        if regex.search(content) and channel_id not in found_channels:
            try:
                await app.forward_messages(
                    chat_id=channel_id,
                    from_chat_id=source_id,
                    message_ids=[msg.id for msg in messages]
                )
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

async def delayed_flush(grouped_id, source_id):
    await asyncio.sleep(1.5)
    await flush_album(grouped_id, source_id)

@app.on_message(filters.chat(list(main_channels.keys())) & filters.group)
async def message_handler(client, message: Message):
    try:
        grouped_id = message.media_group_id
        source_id = message.chat.id

        if grouped_id:
            group_buffer[grouped_id].append(message)

            if group_timers.get(grouped_id):
                group_timers[grouped_id].cancel()

            group_timers[grouped_id] = asyncio.create_task(delayed_flush(grouped_id, source_id))
        else:
            await process_and_forward([message], source_id)
    except Exception as e:
        logging.error(f"💥 Error in group handler: {e}")

@app.on_message(filters.chat(list(main_channels.keys())) & filters.private)
async def private_handler(client, message: Message):
    try:
        await process_and_forward([message], message.chat.id)
    except Exception as e:
        logging.error(f"💥 Error in private handler: {e}")

async def main():
    await app.start()
    logging.info("✅ Bot started. Listening for messages...")
    await asyncio.Event().wait()  # Keeps the bot running

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("🛑 Bot stopped")
