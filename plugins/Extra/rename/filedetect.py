# Don't Remove Credit @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot @Tech_VJ
# Ask Doubt on telegram @KingVJ01

from pyrogram import Client, filters
from pyrogram.enums import MessageMediaType
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ForceReply

async def refunc(client, message, new_name, msg):
    # NOTE: the original code referenced `out_filename` before it was ever
    # assigned (NameError on every call), so the extension-stripping branch
    # never ran. The name is now built first, then the picker is shown.
    try:
        file = getattr(msg, msg.media.value)
        filename = file.file_name
        types = file.mime_type.split("/")
        mime = types[0]
        try:
            base = new_name
            for ext in (".mp4", ".mkv"):
                if ext in base:
                    base = base.replace(ext, "")
            if "." in base:
                base = base.replace(".", "")
            out_name = filename.split(".")[-1]
            out_filename = base + "." + out_name
        except Exception:
            await message.reply_text("**Error** :  No  Extension in File, Not Supporting")
            return
        if mime == "video":
            markup = InlineKeyboardMarkup([[
                InlineKeyboardButton("📁 Document", callback_data="upload_document"),
                InlineKeyboardButton("🎥 Video", callback_data="upload_video")]])
        elif mime == "audio":
            markup = InlineKeyboardMarkup([[InlineKeyboardButton(
                "📁 Document", callback_data="upload_document"), InlineKeyboardButton("🎵 audio", callback_data="upload_audio")]])
        else:
            markup = InlineKeyboardMarkup(
                [[InlineKeyboardButton("📁 Document", callback_data="upload_document")]])
        await message.reply_text(f"**Select the output file type**\n**🎞New Name** :- ```{out_filename}```", reply_to_message_id=msg.id, reply_markup=markup)
    except Exception as e:
        print(f"error: {e}")
