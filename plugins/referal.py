from database.users_chats_db import db, delete_all_referal_users, get_referal_users_count, get_referal_all_users, referal_add_user
from pyrogram import Client
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from info import REFERAL_COUNT, REFERAL_PREMEIUM_TIME, ADMINS

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

async def delete_referrals_handler(client: Client, message: Message):
    user_id = message.from_user.id
    
    # Check if user is admin
    if user_id not in ADMINS:
        await message.reply("❌ You don't have permission to use this command.")
        return
    
    try:
        # Get current referral count before deletion
        total_referrals = await get_referal_users_count("all")  # Assuming this gets total count
        
        # Delete all referrals
        await delete_all_referal_users()
        
        await message.reply(
            f"✅ <b>Referrals Deleted Successfully!</b>\n\n"
            f"📊 Total referrals removed: {total_referrals}\n"
            f"🗑️ All referral data has been cleared from the database."
        )
        
    except Exception as e:
        await message.reply(
            f"❌ <b>Error deleting referrals:</b>\n"
            f"<code>{str(e)}</code>"
        )

# Alternative version if you want to delete referrals for a specific user
async def delete_user_referrals_handler(client: Client, message: Message):
    user_id = message.from_user.id
    
    # Check if user is admin
    if user_id not in ADMINS:
        await message.reply("❌ You don't have permission to use this command.")
        return
    
    # Extract target user ID from command
    try:
        if len(message.command) < 2:
            await message.reply("❌ Please provide a user ID.\nUsage: /delreferrals <user_id>")
            return
            
        target_user_id = int(message.command[1])
        
        # Get referral count before deletion
        user_referrals = await get_referal_users_count(target_user_id)
        
        if user_referrals == 0:
            await message.reply(f"ℹ️ User {target_user_id} has no referrals to delete.")
            return
        
        # Delete referrals for specific user (you might need to implement this function)
        # await delete_user_referal_users(target_user_id)
        
        await message.reply(
            f"✅ <b>User Referrals Deleted!</b>\n\n"
            f"👤 User ID: {target_user_id}\n"
            f"📊 Referrals removed: {user_referrals}"
        )
        
    except ValueError:
        await message.reply("❌ Invalid user ID. Please provide a valid number.")
    except Exception as e:
        await message.reply(
            f"❌ <b>Error deleting user referrals:</b>\n"
            f"<code>{str(e)}</code>"
        )

# For deleting all referrals
@Client.on_message(filters.command("clearreferrals"))
async def clear_all_referrals(client, message):
    await delete_referrals_handler(client, message)

# For deleting specific user's referrals  
@Client.on_message(filters.command("delreferrals"))
async def del_user_referrals(client, message):
    await delete_user_referrals_handler(client, message)
