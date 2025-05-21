

from plugins.Extra.utils import progress_for_pyrogram, convert, humanbytes
from pyrogram import Client, filters
from pyrogram.types import (  InlineKeyboardButton, InlineKeyboardMarkup,ForceReply)
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from database.users_chats_db import db
import os 
import humanize
from PIL import Image
import time
import logging
logger = logging.getLogger(__name__)
logging.getLogger("pyrogram").setLevel(logging.WARNING)

@Client.on_callback_query(filters.regex("upload"))
async def doc(bot, update):
    try:
        # Safe parsing of callback data
        data_parts = update.data.split("_")
        if len(data_parts) != 2:
            await update.answer("❌ Invalid data format.", show_alert=True)
            return

        type = data_parts[1]
        new_name = update.message.text
        if ":-" not in new_name:
            await update.message.edit("❌ Invalid file name format. Expecting `filename:-NewName.ext`")
            return

        new_filename = new_name.split(":-", 1)[1].strip()
        file = update.message.reply_to_message
        file_path = f"downloads/{new_filename}"
        ms = await update.message.edit("⚠️__**Please wait...**__\n\n__Downloading file to my server...__")
        c_time = time.time()
        try:
            path = await bot.download_media(
                message=file,
                progress=progress_for_pyrogram,
                progress_args=("**⚠️ Please wait VJ Hack is in processing**", ms, c_time))
        except Exception as e:
            await ms.edit(str(e))
            return

        old_file_name = path
        os.rename(old_file_name, file_path)

        duration = 0
        try:
            metadata = extractMetadata(createParser(file_path))
            if metadata and metadata.has("duration"):
                duration = metadata.get('duration').seconds
        except:
            pass

        user_id = int(update.message.chat.id)
        ph_path = None
        media = getattr(file, file.media.value)
        filesize = humanize.naturalsize(media.file_size)
        c_caption = await db.get_caption(user_id)
        c_thumb = await db.get_thumbnail(user_id)

        if c_caption:
            try:
                caption = c_caption.format(filename=new_filename, filesize=filesize, duration=convert(duration))
            except Exception as e:
                await ms.edit(text=f"❌ Caption format error: {e}")
                return
        else:
            caption = f"**{new_filename}**"

        if media.thumbs or c_thumb:
            ph_path = await bot.download_media(c_thumb or media.thumbs[0].file_id)
            img = Image.open(ph_path).convert("RGB")
            img = img.resize((320, 320))
            img.save(ph_path, "JPEG")

        await ms.edit("⚠️__**Please wait...**__\n\n__Processing file upload....__")
        c_time = time.time()

        try:
            if type == "document":
                await bot.send_document(
                    update.message.chat.id,
                    document=file_path,
                    thumb=ph_path,
                    caption=caption,
                    progress=progress_for_pyrogram,
                    progress_args=("⚠️ Uploading...", ms, c_time))
            elif type == "video":
                await bot.send_video(
                    update.message.chat.id,
                    video=file_path,
                    caption=caption,
                    thumb=ph_path,
                    duration=duration,
                    progress=progress_for_pyrogram,
                    progress_args=("⚠️ Uploading...", ms, c_time))
            elif type == "audio":
                await bot.send_audio(
                    update.message.chat.id,
                    audio=file_path,
                    caption=caption,
                    thumb=ph_path,
                    duration=duration,
                    progress=progress_for_pyrogram,
                    progress_args=("⚠️ Uploading...", ms, c_time))
        except Exception as e:
            await ms.edit(f"❌ Upload error: {e}")
            if os.path.exists(file_path): os.remove(file_path)
            if ph_path and os.path.exists(ph_path): os.remove(ph_path)
            return

        await ms.delete()
        if os.path.exists(file_path): os.remove(file_path)
        if ph_path and os.path.exists(ph_path): os.remove(ph_path)
    except Exception as e:
        logger.error(f"error : {e}")
