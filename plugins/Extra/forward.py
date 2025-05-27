# Don't Remove Credit @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot @Tech_VJ
# Ask Doubt on telegram @KingVJ01

import asyncio
import logging
import re
from collections import defaultdict
from datetime import datetime

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery

# Assuming you already have this:
# from somewhere import client  # your existing Client instance

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')

# === DATA STRUCTURES ===
main_channels = {}  # source_id -> dest_id
keyword_channels = {}  # tuple(words) -> channel_id
compiled_keywords = []
file_caption = "**Forwarded File**"
group_buffer = defaultdict(list)
group_timers = {}
last_forward_status = {}

# For tracking which user is currently inputting what setting
set_parse = {}

# === UTILITIES ===

def recompile_keywords():
    global compiled_keywords
    compiled_keywords = [
        (re.compile(rf'\b({"|".join(words)})\b', flags=re.IGNORECASE), channel)
        for words, channel in keyword_channels.items()
    ]

def extract_text_and_filenames(messages):
    text_parts = []
    filenames = []

    for msg in messages:
        if msg.text:
            text_parts.append(msg.text)

        if msg.document and msg.document.file_name:
            filenames.append(msg.document.file_name)

    return " ".join(text_parts + filenames)

async def process_and_forward(messages, source_id):
    dest_id = main_channels.get(source_id)
    if not dest_id:
        return

    status_info = {
        "destination": dest_id,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "keywords_matched": [],
        "errors": []
    }

    try:
        await client.forward_messages(chat_id=dest_id, from_chat_id=source_id, message_ids=[msg.message_id for msg in messages])
        logging.info(f"📦 Forwarded from {source_id} → {dest_id}")
    except Exception as e:
        logging.error(f"❌ Forward error {source_id} → {dest_id}: {e}")
        status_info["errors"].append(str(e))

    content = extract_text_and_filenames(messages)
    found_channels = set()

    for regex, channel_id in compiled_keywords:
        if regex.search(content) and channel_id not in found_channels:
            try:
                await client.forward_messages(chat_id=channel_id, from_chat_id=source_id, message_ids=[msg.message_id for msg in messages])
                logging.info(f"🔑 Keyword matched {regex.pattern} → {channel_id}")
                status_info["keywords_matched"].append((regex.pattern, channel_id))
                found_channels.add(channel_id)
            except Exception as e:
                logging.error(f"❌ Keyword forward error to {channel_id}: {e}")
                status_info["errors"].append(str(e))

    last_forward_status[source_id] = status_info
    await asyncio.sleep(3)  # throttle

async def flush_album(grouped_id, source_id):
    messages = group_buffer.pop(grouped_id, [])
    group_timers.pop(grouped_id, None)
    if messages:
        await process_and_forward(messages, source_id)

# === HANDLERS ===

@Client.on_message(filters.chat(list(main_channels.keys())) & ~filters.edited_messages)
async def message_handler(client_, message: Message):
    grouped_id = getattr(message, "media_group_id", None)
    source_id = message.chat.id

    if grouped_id:
        group_buffer[grouped_id].append(message)
        # reset timer
        if group_timers.get(grouped_id):
            group_timers[grouped_id].cancel()

        loop = asyncio.get_event_loop()
        group_timers[grouped_id] = loop.call_later(
            1.5, lambda: asyncio.create_task(flush_album(grouped_id, source_id))
        )
    else:
        await process_and_forward([message], source_id)

# === SETTINGS MENU ===

@Client.on_message(filters.command("fsettings") & filters.private)
async def open_settings(client_, message: Message):
    buttons = [
        [InlineKeyboardButton("➕ Add Main Channel", callback_data="add_main")],
        [InlineKeyboardButton("➕ Add Keyword Channel", callback_data="add_keyword")],
        [InlineKeyboardButton("✏️ Set File Caption", callback_data="set_caption")],
        [InlineKeyboardButton("📊 View Status", callback_data="view_status")],
        [InlineKeyboardButton("📖 Help", callback_data="help_info")]
    ]
    await message.reply("⚙️ **Bot Settings**:\nChoose an option below:", reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query()
async def callback_handler(client_, callback_query: CallbackQuery):
    data = callback_query.data
    user_id = callback_query.from_user.id

    if data == "add_main":
        await callback_query.message.reply("📝 Send source and destination chat IDs separated by space:\nExample: `-100123456 -100654321`")
        set_parse[user_id] = "add_main"
    elif data == "add_keyword":
        await callback_query.message.reply("📝 Send destination channel ID and comma-separated keywords:\nExample: `-100123456 word1,word2,word3`")
        set_parse[user_id] = "add_keyword"
    elif data == "set_caption":
        await callback_query.message.reply("📝 Send the new default caption text:")
        set_parse[user_id] = "set_caption"
    elif data == "view_status":
        await show_status(callback_query.message)
    elif data == "help_info":
        help_text = (
            "📖 **Bot Help Guide**\n\n"
            "**1. Add Main Channel**\n"
            "`<source_chat_id> <destination_chat_id>`\n"
            "_Example:_ `-100123456 -100987654`\n\n"
            "**2. Add Keyword Filters**\n"
            "`<destination_chat_id> word1,word2,word3`\n"
            "_Example:_ `-100123456 news,update`\n\n"
            "**3. Set File Caption**\n"
            "Send any text. This caption will be used for forwarded files.\n\n"
            "**🔎 How Filtering Works**\n"
            "- If keywords in a message match filters, message is forwarded to that channel.\n"
            "- Messages from main channels are forwarded to their destination.\n\n"
            "ℹ️ Use buttons to manage settings easily."
        )
        await callback_query.message.reply(help_text, disable_web_page_preview=True)
    else:
        await callback_query.answer("❓ Unknown option.", show_alert=True)
        return

    await callback_query.answer()

@Client.on_message(filters.private & ~filters.command(["fsettings"]))
async def handle_user_input(client_, message: Message):
    user_id = message.from_user.id
    if user_id not in set_parse:
        return

    action = set_parse.pop(user_id)

    if action == "add_main":
        try:
            src, dst = map(int, message.text.split())
            main_channels[src] = dst
            await message.reply(f"✅ Added main channel:\n`{src}` → `{dst}`")
        except Exception:
            await message.reply("⚠️ Invalid format.\nSend: `<source_id> <dest_id>`")

    elif action == "add_keyword":
        try:
            ch_id_str, keywords_str = message.text.split(maxsplit=1)
            ch_id = int(ch_id_str)
            words = tuple(w.strip() for w in keywords_str.split(",") if w.strip())
            if not words:
                raise ValueError("No keywords")
            keyword_channels[words] = ch_id
            recompile_keywords()
            await message.reply(f"✅ Added keyword filter:\n`{', '.join(words)}` → `{ch_id}`")
        except Exception:
            await message.reply("⚠️ Invalid format.\nSend: `<channel_id> word1,word2,...`")

    elif action == "set_caption":
        global file_caption
        file_caption = message.text
        await message.reply("✅ File caption updated.")

async def show_status(message: Message):
    report = ["📊 **Forwarding Status Report**\n"]

    if main_channels:
        report.append("**Main Channels:**")
        for src, dst in main_channels.items():
            report.append(f"  - `{src}` → `{dst}`")
    else:
        report.append("**Main Channels:** None configured.")

    if keyword_channels:
        report.append("\n**Keyword Channels:**")
        for words, ch in keyword_channels.items():
            report.append(f"  - `{', '.join(words)}` → `{ch}`")
    else:
        report.append("\n**Keyword Channels:** None configured.")

    if last_forward_status:
        report.append("\n**Last Forward Attempts:**")
        for src, info in last_forward_status.items():
            report.append(f"\n🔹 From `{src}` to `{info['destination']}` at `{info['timestamp']}`")
            if info["keywords_matched"]:
                for pat, ch in info["keywords_matched"]:
                    report.append(f"   🔑 Matched `{pat}` → `{ch}`")
            if info["errors"]:
                for err in info["errors"]:
                    report.append(f"   ❌ Error: `{err}`")
    else:
        report.append("\nℹ️ No forwards attempted yet.")

    await message.reply("\n".join(report))
