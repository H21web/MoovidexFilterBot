# Don't Remove Credit @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot @Tech_VJ
# Ask Doubt on telegram @KingVJ01

import logging
import re
import asyncio
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import (
    FloodWait,
    PeerIdInvalid,
    ChannelInvalid,
    ChatAdminRequired
)

# ===== CONFIGURATION =====
class Config:
    # Get these from https://my.telegram.org
    API_ID = 8281168
    API_HASH = "445ff67ec34858448ac184c7479ce917"
    
    # Generate with generate_session.py
    USER_SESSION = "1BVtsOIoBu4X-B021hLB4we-WRkOtYT5VJlHOpp8P6AKXHt5Jdoo2VGurK65sa_iGe5Hnl_idFdc8xLtkLUhnx74iI8NSuxb98OHIEXul3ikz1BNHm3CNiIXKftpxd_cia-fyFA4VZpNFIU8-S2gdtQnCTwcZQpgSbBcCE1evohvQHS3XcHumam1nGVki4Xr2LZhP98oyXJVbw8dfucZZ4XWT9NltQbfOd9Mvyn3qO-3lSpP-gm-bQayaGhD-RhThsCGxOgObbg5Xy0zu-x9EXWJ-DTcoGid0feaRtqryrRi2_Evr_D2qAPH1SE2GstPSxGPbIi4TBspn_1ot9V6A450vgdt6tsU="  
    
    # Get from @BotFather
    BOT_TOKEN = "7898813406:AAEGLvPOVeJlDKaztJdS4OSv43xIk-2xbZo"  
    
    # Your Telegram ID
    ADMIN_ID = 1011394081  
    OWNER_ID = 1011394081  
    
    # Channel links for caption
    CHANNEL_LINK = "https://t.me/moovidex"  
    
    # Channel mapping: {source_id: [dest_id1, dest_id2]}
    CHANNEL_MAPPING = {
        -1002570431865: [-1002540224499],
        # Add more mappings as needed
    }

# ===== LOGGING SETUP =====
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("forwarder.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ===== GLOBAL TRACKERS =====
class ForwardStats:
    total_forwarded = 0
    last_forwarded = None
    errors = 0
    channel_stats = {}
    
    @classmethod
    def init_stats(cls):
        for src_id, dest_ids in Config.CHANNEL_MAPPING.items():
            cls.channel_stats[src_id] = {
                "name": f"Channel {src_id}",
                "destinations": {dest_id: {"count": 0, "last_forwarded": None} for dest_id in dest_ids},
                "total_forwarded": 0,
                "errors": 0
            }

ForwardStats.init_stats()

# ===== CLIENT SETUP =====
user_client = Client(
    name="user_account",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    session_string=Config.USER_SESSION,
    in_memory=True
)

bot = Client(
    name="forward_bot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN
)

# ===== HELPER FUNCTIONS =====
def human_readable_size(size):
    """Convert bytes to readable format (e.g., 1.2 MB)"""
    if not size: return "N/A"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"

def format_time(dt):
    """Format datetime for display"""
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else "Never"

def clean_caption(text):
    """Remove URLs and usernames from text"""
    if not text: return ""
    text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', "[LINK REMOVED]", text)
    text = re.sub(r'@(\w+)', "[USER REMOVED]", text)
    return text

# ===== CORE FORWARDING LOGIC =====
async def forward_message(message: Message):
    """Handle media forwarding with retry logic"""
    if not (message.document or message.video):
        return False

    file = message.document or message.video
    file_name = getattr(file, "file_name", f"Media_{file.file_id}")
    file_size = human_readable_size(file.file_size)
    original_caption = clean_caption(message.caption or "")
    
    new_caption = f"""**{file_name}** ({file_size})
────────────────────
{original_caption}
────────────────────
🔗 {Config.CHANNEL_LINK}"""

    source_chat = message.chat.id
    if source_chat not in Config.CHANNEL_MAPPING:
        return False

    success = False
    for dest_chat in Config.CHANNEL_MAPPING[source_chat]:
        try:
            # Forward using user account
            await user_client.forward_messages(
                chat_id=dest_chat,
                from_chat_id=source_chat,
                message_ids=message.id
            )
            
            # Update caption (separate request)
            async for msg in user_client.search_messages(dest_chat, limit=1):
                if msg.caption != new_caption:
                    await msg.edit_caption(new_caption)
            
            # Update statistics
            ForwardStats.total_forwarded += 1
            ForwardStats.last_forwarded = datetime.now()
            ForwardStats.channel_stats[source_chat]["total_forwarded"] += 1
            ForwardStats.channel_stats[source_chat]["destinations"][dest_chat]["count"] += 1
            ForwardStats.channel_stats[source_chat]["destinations"][dest_chat]["last_forwarded"] = datetime.now()
            
            logger.info(f"Forwarded to {dest_chat}")
            success = True
            
        except FloodWait as e:
            logger.warning(f"Flood wait: Sleeping {e.value} seconds")
            await asyncio.sleep(e.value)
        except (PeerIdInvalid, ChannelInvalid, ChatAdminRequired) as e:
            logger.error(f"Forward failed to {dest_chat}: {str(e)}")
            ForwardStats.errors += 1
            ForwardStats.channel_stats[source_chat]["errors"] += 1
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            ForwardStats.errors += 1
            ForwardStats.channel_stats[source_chat]["errors"] += 1
    
    return success

# ===== BOT COMMANDS =====
@bot.on_message(filters.command("start") & filters.private)
async def start_command(client: Client, message: Message):
    await message.reply("""🚀 **Media Forwarder Bot**
    
- Automatically forwards new media files
- Use /forwardpast to process old messages
- /forwardstats to view statistics""")

@bot.on_message(filters.command("forwardpast") & filters.user([Config.ADMIN_ID, Config.OWNER_ID]))
async def forward_past(client: Client, message: Message):
    try:
        args = message.text.split()
        if len(args) < 2:
            await message.reply("**Usage:** `/forwardpast 100` (max 1000)")
            return

        limit = min(int(args[1]), 1000)
        source_chat = message.chat.id if message.chat.id in Config.CHANNEL_MAPPING else None
        
        if not source_chat:
            await message.reply("❌ Channel not configured!")
            return

        progress = await message.reply(f"⏳ Processing last {limit} messages...")
        processed = 0

        async for old_msg in user_client.get_chat_history(source_chat, limit=limit):
            if await forward_message(old_msg):
                processed += 1
                if processed % 10 == 0:
                    await progress.edit(f"🔄 Processed {processed}/{limit} messages...")

        await progress.edit(f"✅ Forwarded {processed}/{limit} media files")

    except Exception as e:
        logger.error(f"/forwardpast error: {str(e)}", exc_info=True)
        await message.reply("❌ Processing failed!")

@bot.on_message(filters.command("forwardstats") & filters.user([Config.ADMIN_ID, Config.OWNER_ID]))
async def show_stats(client: Client, message: Message):
    stats = []
    stats.append(f"📊 **Forwarding Statistics**")
    stats.append(f"• Total Forwarded: `{ForwardStats.total_forwarded}`")
    stats.append(f"• Last Activity: `{format_time(ForwardStats.last_forwarded)}`")
    stats.append(f"• Errors: `{ForwardStats.errors}`\n")

    for src_id, data in ForwardStats.channel_stats.items():
        stats.append(f"📌 **{data['name']}** (`{src_id}`)")
        stats.append(f"   ➠ Forwarded: `{data['total_forwarded']}`")
        stats.append(f"   ➠ Errors: `{data['errors']}`")
        
        for dest_id, dest_data in data["destinations"].items():
            stats.append(f"      ├─➤ `{dest_id}`")
            stats.append(f"      │   ➠ Count: `{dest_data['count']}`")
            stats.append(f"      │   ➠ Last: `{format_time(dest_data['last_forwarded'])}`")

    await message.reply_text("\n".join(stats), disable_web_page_preview=True)

# ===== EVENT HANDLERS =====
@user_client.on_message(filters.channel & filters.incoming)
async def handle_new_message(client: Client, message: Message):
    if message.chat.id in Config.CHANNEL_MAPPING:
        await forward_message(message)

# ===== MAIN FUNCTION =====
async def main():
    await asyncio.gather(
        user_client.start(),
        bot.start()
    )
    logger.info("Bot and user client started successfully")
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.critical(f"Fatal error: {str(e)}", exc_info=True)
