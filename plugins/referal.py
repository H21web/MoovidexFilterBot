from database.users_chats_db import db, delete_all_referal_users, get_referal_users_count, get_referal_all_users, referal_add_user
from pyrogram import Client
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from info import REFERAL_COUNT,REFERAL_PREMEIUM_TIME, ADMINS

async def invite_handler(client: Client, message: Message):
    bot_username = (await client.get_me()).username
    user_id = message.from_user.id

    referral_link = f"https://t.me/{bot_username}?start=MVDEX-{user_id}"
    num_referrals = await get_referal_users_count(user_id)

    buttons = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔗 Share Invite Link", url=f"https://t.me/share/url?url={referral_link}")]]
    )

    await message.reply(
        "<b>👤 Your Referral Program</b>\n\n"
        f"🔗 Link: <code>{referral_link}</code>\n"
        f"👥 Referrals: {num_referrals}/{REFERAL_COUNT}\n"
        f"🎁 Reward: Premium for {REFERAL_PREMEIUM_TIME}\n\n"
        "Invite friends to unlock premium! 🚀",
        reply_markup=buttons
    )

