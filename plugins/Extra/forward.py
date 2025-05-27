import asyncio
import re
import random
import logging
from collections import defaultdict
from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import RPCError
from pyrogram.enums import MessageMediaType
from TechVJ.bot import TechVJBot as Client



# Logging setup
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')

# Dynamic settings
main_channels = {}  # source_id: dest_id
keyword_channels = {}  # keywords (tuple): dest_id
compiled_keywords = []
file_filter_exts = []  # e.g., ['.mkv', '.mp4']
caption_template = "{file_name}"

# Message group buffers (for albums)
group_buffer = defaultdict(list)
group_timers = {}

# --- UTILITY FUNCTIONS ---
def update_compiled_keywords():
    global compiled_keywords
    compiled_keywords = [
        (re.compile(rf"\\b({'|'.join(words)})\\b", flags=re.IGNORECASE), channel)
        for words, channel in keyword_channels.items()
    ]

def extract_text_and_filenames(messages):
    text_parts = []
    filenames = []
    for msg in messages:
        if msg.text:
            text_parts.append(msg.text)
        if msg.media and msg.media in [MessageMediaType.DOCUMENT, MessageMediaType.VIDEO, MessageMediaType.AUDIO]:
            file_name = msg.document.file_name if msg.document else msg.video.file_name if msg.video else None
            if file_name:
                filenames.append(file_name)
    return " ".join(text_parts + filenames)

def file_passes_filter(msg: Message) -> bool:
    if not file_filter_exts:
        return True
    file_name = msg.document.file_name if msg.document else None
    return file_name and any(file_name.lower().endswith(ext) for ext in file_filter_exts)

async def process_and_forward(messages, source_id):
    dest_id = main_channels.get(source_id)
    if not dest_id:
        return

    for msg in messages:
        if not file_passes_filter(msg):
            continue

        try:
            await msg.copy(dest_id)
            logging.info(f"Forwarded from {source_id} to {dest_id}")
        except RPCError as e:
            logging.error(f"Forward error to {dest_id}: {e}")

        content = extract_text_and_filenames([msg])
        for regex, channel_id in compiled_keywords:
            if regex.search(content):
                try:
                    await msg.copy(channel_id)
                    logging.info(f"Keyword match → forwarded to {channel_id}")
                except RPCError as e:
                    logging.error(f"Keyword forward error to {channel_id}: {e}")

    await asyncio.sleep(random.uniform(3, 5))

async def flush_album(grouped_id, source_id):
    messages = group_buffer.pop(grouped_id, [])
    group_timers.pop(grouped_id, None)
    if messages:
        await process_and_forward(messages, source_id)

@Client.on_message(filters.chat(list(main_channels.keys())))
async def message_handler(client, msg):
    grouped_id = msg.media_group_id
    source_id = msg.chat.id

    if grouped_id:
        group_buffer[grouped_id].append(msg)
        if group_timers.get(grouped_id):
            group_timers[grouped_id].cancel()

        group_timers[grouped_id] = asyncio.get_event_loop().call_later(
            1.5, lambda: asyncio.create_task(flush_album(grouped_id, source_id))
        )
    else:
        await process_and_forward([msg], source_id)

@Client.on_message(filters.command("fsettings") & filters.private)
async def open_settings(client, msg):
    buttons = [
        [InlineKeyboardButton("Add Main Channel", callback_data="add_main")],
        [InlineKeyboardButton("Add Keyword", callback_data="add_kw")],
        [InlineKeyboardButton("Set File Filters", callback_data="set_filter")],
        [InlineKeyboardButton("Set Caption", callback_data="set_caption")],
        [InlineKeyboardButton("View Config", callback_data="view_config")],
        [InlineKeyboardButton("Help", callback_data="help")],
    ]
    await msg.reply("⚙️ Settings Menu", reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query()
async def callback_handler(client, callback: CallbackQuery):
    user_id = callback.from_user.id
    data = callback.data

    if data == "add_main":
        await callback.message.reply("Send in the format: `source_id dest_id`.", quote=True)
    elif data == "add_kw":
        await callback.message.reply("Send in the format: `word1,word2,... dest_id`.", quote=True)
    elif data == "set_filter":
        await callback.message.reply("Send file extensions separated by comma (e.g., `.mkv,.mp4`) to filter files.", quote=True)
    elif data == "set_caption":
        await callback.message.reply("Send caption template. Use `{file_name}` as placeholder.", quote=True)
    elif data == "view_config":
        kw_info = "\n".join([f"{k} → {v}" for k, v in keyword_channels.items()])
        mc_info = "\n".join([f"{k} → {v}" for k, v in main_channels.items()])
        await callback.message.reply(f"📥 Main Channels:\n{mc_info}\n\n🔑 Keywords:\n{kw_info}\n\n📁 Filters: {', '.join(file_filter_exts)}\n📝 Caption: {caption_template}")
    elif data == "help":
        help_text = (
            "📌 **Bot Instructions**\n"
            "1. Use `/fsettings` to open the settings menu.\n"
            "2. Use buttons to add channels, keywords, file filters, and captions.\n"
            "3. For album messages, the bot waits for all files before forwarding.\n"
            "4. Keywords are matched in message text and file names.\n"
            "5. File filters limit which file types are forwarded.\n"
            "6. You can view the current configuration anytime from the settings."
        )
        await callback.message.reply(help_text)
    await callback.answer()

@Client.on_message(filters.private & filters.text)
async def settings_input_handler(client, msg):
    global caption_template
    if " " in msg.text and msg.text.split(" ")[0].isdigit():
        try:
            src, dst = map(int, msg.text.split())
            main_channels[src] = dst
            await msg.reply(f"✅ Main channel added: {src} → {dst}")
        except:
            await msg.reply("❌ Failed to add. Use format: `source_id dest_id`")
    elif "," in msg.text and msg.text.split()[1].isdigit():
        try:
            parts = msg.text.split()
            words = tuple(parts[0].split(","))
            dest = int(parts[1])
            keyword_channels[words] = dest
            update_compiled_keywords()
            await msg.reply(f"✅ Keyword added: {words} → {dest}")
        except:
            await msg.reply("❌ Failed to add keyword. Format: `word1,word2,... dest_id`")
    elif msg.text.startswith("."):
        file_filter_exts.clear()
        file_filter_exts.extend([ext.strip().lower() for ext in msg.text.split(",")])
        await msg.reply(f"✅ File filter updated: {', '.join(file_filter_exts)}")
    elif "{file_name}" in msg.text:
        caption_template = msg.text
        await msg.reply("✅ Caption template updated.")

