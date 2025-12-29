from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from info import ADMINS, URL
from Script import script

@Client.on_message(filters.command("dashboard") & filters.user(ADMINS))
async def dashboard_command(client, message):
    dash_url = URL + "admin" if URL.endswith("/") else URL + "/admin"
    
    btn = [[
        InlineKeyboardButton("📊 Open Dashboard", url=dash_url)
    ]]
    
    await message.reply_text(
        text=script.DASHBOARD_TXT,
        reply_markup=InlineKeyboardMarkup(btn),
        quote=True
    )
