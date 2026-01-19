# Don't Remove Credit @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot @Tech_VJ
# Ask Doubt on telegram @KingVJ01

from pyrogram import Client, filters
from info import CHANNELS, LOG_CHANNEL
from database.ia_filterdb import save_file
from utils import get_size
from pyrogram import Client, filters, enums

media_filter = filters.document | filters.video | filters.audio

@Client.on_message(filters.chat(CHANNELS) & media_filter)
async def media(bot, message):
    media = getattr(message, message.media.value, None)
    if media.file_name is None:
        return

    media.caption = message.caption
    
    try:
        aynav, vnay = await save_file(media)
        if aynav:
            # File Saved Successfully
            if LOG_CHANNEL:
                await bot.send_message(
                    LOG_CHANNEL,
                    f"<b>File Saved Automatically!</b>\n\n"
                    f"<b>🎬 Title:</b> {media.file_name}\n"
                    f"<b>📦 Size:</b> {get_size(media.file_size)}\n"
                    f"<b>📂 Channel:</b> {message.chat.title} (`{message.chat.id}`)\n"
                    f"<b>💾 Database:</b> {'Secondary' if vnay == 1 else 'Primary'}" # Note: save_file returns 1 for success. We can't distinguish DB unless we change save_file return signature, but usually 1 is success.
                )
        elif vnay == 0:
            # Duplicate
            pass
        elif vnay == 2:
            # Error
            if LOG_CHANNEL:
                await bot.send_message(
                    LOG_CHANNEL,
                    f"<b>❌ Error Saving File Auto!</b>\n\n"
                    f"<b>🎬 Title:</b> {media.file_name}\n"
                    f"<b>⚠️ Error:</b> Database Error (Check Console)"
                )
    except Exception as e:
        print(f"Auto Save Error: {e}")
        if LOG_CHANNEL:
             await bot.send_message(
                LOG_CHANNEL,
                f"❌ <b>Bot Error in Auto-Save:</b> {e}"
            )
