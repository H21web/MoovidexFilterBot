import asyncio
from pyrogram import Client, filters, enums
from pyrogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, BotCommand
)
from utils import is_check_admin
from Script import script
from info import ADMINS


@Client.on_message(filters.command('grp_cmds'))
async def grp_cmds(client, message):
    user_id = message.from_user.id if message.from_user else None
    if not user_id:
        return await message.reply("<b>💔 ʏᴏᴜ ᴀʀᴇ ᴀɴᴏɴʏᴍᴏᴜꜱ ᴀᴅᴍɪɴ ʏᴏᴜ ᴄᴀɴ'ᴛ ᴜꜱᴇ ᴛʜɪꜱ ᴄᴏᴍᴍᴀɴᴅ...</b>")
    
    chat_type = message.chat.type
    if chat_type not in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        return await message.reply_text("<code>ᴜꜱᴇ ᴛʜɪꜱ ᴄᴏᴍᴍᴀɴᴅ ɪɴ ɢʀᴏᴜᴘ.</code>")
    
    grp_id = message.chat.id
    if not await is_check_admin(client, grp_id, message.from_user.id):
        return await message.reply_text('<b>ʏᴏᴜ ᴀʀᴇ ɴᴏᴛ ᴀᴅᴍɪɴ ɪɴ ᴛʜɪꜱ ɢʀᴏᴜᴘ</b>')

    buttons = [[
        InlineKeyboardButton('❌ ᴄʟᴏsᴇ ❌', callback_data='close_data')
    ]]
    await message.reply_text(
        text=script.GROUP_C_TEXT,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=enums.ParseMode.HTML
    )


@Client.on_message(filters.command("admin_cmds") & filters.user(ADMINS))
async def admin_cmds(client, message):
    buttons = [
        [KeyboardButton("/add_premium"), KeyboardButton("/premium_users")],
        [KeyboardButton("/remove_premium"), KeyboardButton("/add_redeem")],
        [KeyboardButton("/refresh"), KeyboardButton("/set_muc")],
        [KeyboardButton("/pm_search_on"), KeyboardButton("/pm_search_off")],
        [KeyboardButton("/set_ads"), KeyboardButton("/del_ads")],
        [KeyboardButton("/setlist"), KeyboardButton("/clearlist")],
        [KeyboardButton("/verify_id"), KeyboardButton("/index")],
        [KeyboardButton("/send"), KeyboardButton("/leave")],
        [KeyboardButton("/ban"), KeyboardButton("/unban")],
        [KeyboardButton("/broadcast"), KeyboardButton("/grp_broadcast")],
        [KeyboardButton("/delreq"), KeyboardButton("/channel")],
        [KeyboardButton("/del_file"), KeyboardButton("/delete")],
        [KeyboardButton("/deletefiles"), KeyboardButton("/deleteall")],
        [KeyboardButton("All These Commands Can Be Used Only By Admins.")],
        [KeyboardButton("❌ Close Panel")]  # Close button added
    ]
    reply_markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True)

    sent_message = await message.reply(
        "<b>Admin All Commands [auto delete 2 min] 👇</b>",
        reply_markup=reply_markup,
    )
    await asyncio.sleep(120)
    await sent_message.delete()
    await message.delete()

@Client.on_message(filters.regex("^❌ Closepanel$") & filters.user(ADMINS))
async def close_keyboard(client, message):
    await message.reply(
        "✅ closed.",
        reply_markup=ReplyKeyboardRemove()
    )


@Client.on_callback_query(filters.regex("close_data"))
async def close_inline_keyboard(client, callback_query):
    try:
        await callback_query.message.delete()
    except Exception:
        await callback_query.message.edit_text("❌ Message closed.")


@Client.on_message(filters.command("commands") & filters.user(ADMINS))
async def set_commands(client, message):
    commands = [
        BotCommand("start", "Start The Bot"),
        BotCommand("most", "Get Most Searches Button List"),
        BotCommand("trend", "Get Top Trending Button List"),
        BotCommand("mostlist", "Show Most Searches List"),
        BotCommand("trendlist", "𝖦𝖾𝗍 𝖳𝗈𝗉 𝖳𝗋𝖾𝗇𝖽𝗂𝗇𝗀 𝖡𝗎𝗍𝗍𝗈𝗇 𝖫𝗂𝗌t"),
        BotCommand("plan", "Check Available Premium Membership Plans"),
        BotCommand("myplan", "Check Your Currunt Plan"),
        BotCommand("refer", "To Refer Your Friend And Get Premium"),
        BotCommand("stats", "Check My Database"),
        BotCommand("id", "Get Telegram Id"),
        BotCommand("font", "To Generate Cool Fonts"),
        BotCommand("details", "Check Group Details"),
        BotCommand("settings", "Change Bot Setting"),
        BotCommand("grp_cmds", "Check Group Commands"),
        BotCommand("admin_cmds", "Bot Admin Commands")
    ]
    await client.set_bot_commands(commands)
    await message.reply("✅ Bot commands set successfully.")
