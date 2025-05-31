# Don't Remove Credit @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot @Tech_VJ
# Ask Doubt on telegram @KingVJ01

import logging
import re
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# === CONFIGURATION ===
CHANNEL_MAPPING = {
    -1002570431865: [-1002540224499],  # Format: {source_id: [dest1_id, dest2_id]}
}

ADMIN_ID = 1011394081  # Your Telegram user ID
OWNER_ID = 1011394081  # Bot owner ID (same as above if solo)
CHNL_LNK = "https://t.me/moovidex"  # For captions

# Regex for cleaning captions
URL_PATTERN = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
USERNAME_PATTERN = re.compile(r'@(\w+)')

# Caption template
CAPTION_TEMPLATE = """**{filename}** ({size})
────────────────────
{original_caption}
────────────────────
🔗 {channel_link}"""

# === STATISTICS TRACKING ===
FORWARD_STATS = {
    "total_forwarded": 0,
    "last_forwarded": None,
    "channel_stats": {},
    "errors": 0
}

# Initialize stats
for src_id, dest_ids in CHANNEL_MAPPING.items():
    FORWARD_STATS["channel_stats"][src_id] = {
        "name": f"Channel {src_id}",
        "destinations": {dest_id: {"count": 0, "last_forwarded": None} for dest_id in dest_ids},
        "total_forwarded": 0,
        "errors": 0
    }

# === HELPER FUNCTIONS ===
def human_readable_size(size):
    """Convert bytes to human-readable format (e.g., 1.2 MB)"""
    if not size: return "N/A"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"

def format_time(dt):
    """Format datetime for display"""
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else "Never"

async def forward_message(client: Client, message: Message, source_chat: int):
    """Shared forwarding logic for both new and past messages"""
    try:
        file = message.document or message.video
        file_type = "Document" if message.document else "Video"
        file_name = getattr(file, "file_name", f"{file_type}_{file.file_id}")
        file_size = human_readable_size(file.file_size)
        
        # Clean caption
        original_caption = message.caption or ""
        cleaned_caption = URL_PATTERN.sub("[LINK REMOVED]", original_caption)
        cleaned_caption = USERNAME_PATTERN.sub("[USERNAME REMOVED]", cleaned_caption)
        
        # Apply template
        new_caption = CAPTION_TEMPLATE.format(
            filename=file_name,
            size=file_size,
            original_caption=cleaned_caption,
            channel_link=CHNL_LNK
        )

        # Forward to all destinations
        for dest_chat in CHANNEL_MAPPING[source_chat]:
            try:
                if message.document:
                    await message.document.copy(dest_chat, caption=new_caption)
                else:
                    await message.video.copy(dest_chat, caption=new_caption)
                
                # Update stats
                FORWARD_STATS["total_forwarded"] += 1
                FORWARD_STATS["last_forwarded"] = datetime.now()
                FORWARD_STATS["channel_stats"][source_chat]["total_forwarded"] += 1
                FORWARD_STATS["channel_stats"][source_chat]["destinations"][dest_chat]["count"] += 1
                FORWARD_STATS["channel_stats"][source_chat]["destinations"][dest_chat]["last_forwarded"] = datetime.now()
                
                logger.info(f"Forwarded {file_type} from {source_chat} to {dest_chat}")
                
            except Exception as e:
                logger.error(f"Forward error (Source: {source_chat}, Dest: {dest_chat}): {e}")
                FORWARD_STATS["errors"] += 1
                FORWARD_STATS["channel_stats"][source_chat]["errors"] += 1
                
    except Exception as e:
        logger.error(f"Error in forward_message: {e}")
        raise

# === REAL-TIME FORWARDING ===
@Client.on_message(filters.channel & filters.incoming)
async def handle_new_messages(client: Client, message: Message):
    if message.chat.id in CHANNEL_MAPPING and (message.document or message.video):
        await forward_message(client, message, message.chat.id)

# === PAST MESSAGE FORWARDING ===
@Client.on_message(filters.command("forwardpast") & filters.user([ADMIN_ID, OWNER_ID]))
async def forward_past_messages(client: Client, message: Message):
    try:
        args = message.text.split()
        if len(args) < 2:
            await message.reply("**Usage:** `/forwardpast <limit>` (e.g., `/forwardpast 100`)")
            return

        limit = min(int(args[1]), 1000)  # Telegram limits
        source_chat = message.chat.id if message.chat.id in CHANNEL_MAPPING else None
        
        if not source_chat:
            await message.reply("❌ This channel isn't configured for forwarding!")
            return

        await message.reply(f"⏳ Fetching last {limit} messages...")
        processed = 0

        async for old_msg in client.get_chat_history(source_chat, limit=limit):
            if old_msg.document or old_msg.video:
                await forward_message(client, old_msg, source_chat)
                processed += 1

        await message.reply(f"✅ Forwarded {processed}/{limit} media files.")

    except Exception as e:
        logger.error(f"/forwardpast error: {e}")
        await message.reply("❌ Failed to process past messages!")

# === STATISTICS COMMAND ===
@Client.on_message(filters.command("forwardstats") & filters.user([ADMIN_ID, OWNER_ID]))
async def show_stats(client: Client, message: Message):
    stats_text = "📊 **Forwarding Statistics**\n\n"
    stats_text += f"• **Total Forwarded:** `{FORWARD_STATS['total_forwarded']}`\n"
    stats_text += f"• **Last Forwarded:** `{format_time(FORWARD_STATS['last_forwarded'])}`\n"
    stats_text += f"• **Total Errors:** `{FORWARD_STATS['errors']}`\n\n"

    for src_id, data in FORWARD_STATS["channel_stats"].items():
        stats_text += f"📌 **{data['name']}** (`{src_id}`)\n"
        stats_text += f"   ➠ Forwarded: `{data['total_forwarded']}` | Errors: `{data['errors']}`\n"
        for dest_id, dest_data in data["destinations"].items():
            stats_text += f"      ├─➤ `{dest_id}`: `{dest_data['count']}` (Last: `{format_time(dest_data['last_forwarded'])})`\n"

    await message.reply_text(stats_text, disable_web_page_preview=True)
