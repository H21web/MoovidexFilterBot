from database.users_chats_db import db, delete_all_referal_users, get_referal_users_count, get_referal_all_users, referal_add_user
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from info import REFERAL_COUNT, REFERAL_PREMEIUM_TIME, ADMINS
import asyncio
import logging

logger = logging.getLogger(__name__)

async def invite_handler(client: Client, message: Message):
    try:
        bot_username = (await client.get_me()).username
        user_id = message.from_user.id
        referral_link = f"https://t.me/{bot_username}?start=MVDEX-{user_id}"
        num_referrals = await get_referal_users_count(user_id)
        
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 Share Invite Link", url=f"https://t.me/share/url?url={referral_link}")]
        ])
        
        await message.reply(
            "<b>👤 Your Referral Program</b>\n\n"
            f"🔗 Link: <code>{referral_link}</code>\n"
            f"👥 Referrals: {num_referrals}/{REFERAL_COUNT}\n"
            f"🎁 Reward: Premium for {REFERAL_PREMEIUM_TIME}\n\n"
            "Invite friends to unlock premium! 🚀",
            reply_markup=buttons
        )
    except Exception as e:
        logger.error(f"Error in invite_handler: {e}")
        await message.reply("❌ An error occurred while generating your referral link.")

async def delete_referrals_handler(client: Client, message: Message):
    try:
        user_id = message.from_user.id
        
        # Only admins can delete ALL referrals, regular users can delete their own
        # This function now deletes all referrals (admin only)
        if user_id not in ADMINS:
            await message.reply("❌ Only admins can delete all referrals. Use /clearmyreferrals to delete your own referrals.")
            return
        
        # Send processing message
        processing_msg = await message.reply("🔄 Processing... Deleting all referrals...")
        
        try:
            # Get all referral users to count them
            all_referrals = await get_referal_all_users()
            total_count = len(all_referrals) if all_referrals else 0
            
            if total_count == 0:
                await processing_msg.edit("ℹ️ No referrals found to delete.")
                return
            
            # Delete all referrals
            await delete_all_referal_users()
            
            await processing_msg.edit(
                f"✅ <b>Referrals Deleted Successfully!</b>\n\n"
                f"📊 Total referrals removed: {total_count}\n"
                f"🗑️ All referral data has been cleared from the database."
            )
            
        except Exception as e:
            logger.error(f"Error deleting referrals: {e}")
            await processing_msg.edit(
                f"❌ <b>Error deleting referrals:</b>\n"
                f"<code>{str(e)}</code>"
            )
            
    except Exception as e:
        logger.error(f"Error in delete_referrals_handler: {e}")
        await message.reply("❌ An unexpected error occurred.")

async def delete_user_referrals_handler(client: Client, message: Message):
    try:
        user_id = message.from_user.id
        
        # Allow users to delete their own referrals, admins can delete any user's referrals
        is_admin = user_id in ADMINS
        
        # Parse command arguments
        command_parts = message.text.split()
        
        # If no user ID provided, delete own referrals
        if len(command_parts) < 2:
            target_user_id = user_id  # Delete own referrals
        else:
            try:
                target_user_id = int(command_parts[1])
                # Non-admins can only delete their own referrals
                if not is_admin and target_user_id != user_id:
                    await message.reply("❌ You can only delete your own referrals. Use /clearmyreferrals or /delreferrals without user ID.")
                    return
            except ValueError:
                await message.reply("❌ Invalid user ID. Please provide a valid number.")
                return
        
        # Send processing message
        if target_user_id == user_id:
            processing_msg = await message.reply("🔄 Processing... Deleting your referrals...")
        else:
            processing_msg = await message.reply(f"🔄 Processing... Checking referrals for user {target_user_id}...")
        
        try:
            # Get referral count for the specific user
            user_referrals = await get_referal_users_count(target_user_id)
            
            if user_referrals == 0:
                if target_user_id == user_id:
                    await processing_msg.edit("ℹ️ You have no referrals to delete.")
                else:
                    await processing_msg.edit(f"ℹ️ User {target_user_id} has no referrals to delete.")
                return
            
            # Note: You need to implement delete_user_referal_users function in your database module
            # For now, this is a placeholder that shows what would happen
            if target_user_id == user_id:
                await processing_msg.edit(
                    f"⚠️ <b>Function Not Implemented</b>\n\n"
                    f"👤 Your referrals: {user_referrals}\n\n"
                    f"Please implement <code>delete_user_referal_users(user_id)</code> function in your database module to enable this feature."
                )
            else:
                await processing_msg.edit(
                    f"⚠️ <b>Function Not Implemented</b>\n\n"
                    f"👤 User ID: {target_user_id}\n"
                    f"📊 Found referrals: {user_referrals}\n\n"
                    f"Please implement <code>delete_user_referal_users(user_id)</code> function in your database module to enable this feature."
                )
            
        except Exception as e:
            logger.error(f"Error deleting user referrals: {e}")
            await processing_msg.edit(
                f"❌ <b>Error deleting user referrals:</b>\n"
                f"<code>{str(e)}</code>"
            )
            
    except Exception as e:
        logger.error(f"Error in delete_user_referrals_handler: {e}")
        await message.reply("❌ An unexpected error occurred.")

# Add handler for users to delete their own referrals
async def clear_my_referrals_handler(client: Client, message: Message):
    try:
        user_id = message.from_user.id
        
        # Send processing message
        processing_msg = await message.reply("🔄 Processing... Deleting your referrals...")
        
        try:
            # Get user's referral count
            user_referrals = await get_referal_users_count(user_id)
            
            if user_referrals == 0:
                await processing_msg.edit("ℹ️ You have no referrals to delete.")
                return
            
            # Note: You need to implement delete_user_referal_users function in your database module
            # For now, this is a placeholder
            await processing_msg.edit(
                f"⚠️ <b>Feature Coming Soon</b>\n\n"
                f"👤 Your referrals: {user_referrals}\n\n"
                f"This feature will be available once the database function is implemented."
            )
            
        except Exception as e:
            logger.error(f"Error deleting user's own referrals: {e}")
            await processing_msg.edit(
                f"❌ <b>Error deleting your referrals:</b>\n"
                f"<code>{str(e)}</code>"
            )
            
    except Exception as e:
        logger.error(f"Error in clear_my_referrals_handler: {e}")
        await message.reply("❌ An unexpected error occurred.")

# Command handlers with proper filters
@Client.on_message(filters.command("clearreferrals") & filters.private)
async def clear_all_referrals(client: Client, message: Message):
    await delete_referrals_handler(client, message)

@Client.on_message(filters.command("delreferrals") & filters.private)
async def del_user_referrals(client: Client, message: Message):
    await delete_user_referrals_handler(client, message)

@Client.on_message(filters.command("clearmyreferrals") & filters.private)
async def clear_my_referrals(client: Client, message: Message):
    await clear_my_referrals_handler(client, message)

@Client.on_message(filters.command("invite") & filters.private)
async def invite_command(client: Client, message: Message):
    await invite_handler(client, message)



# Show referral stats - accessible by all users
@Client.on_message(filters.command("refstats") & filters.private)
async def referral_stats(client: Client, message: Message):
    try:
        user_id = message.from_user.id
        is_admin = user_id in ADMINS
        
        processing_msg = await message.reply("🔄 Fetching referral statistics...")
        
        try:
            if is_admin:
                # Admins see global stats
                all_referrals = await get_referal_all_users()
                total_referrals = len(all_referrals) if all_referrals else 0
                user_referrals = await get_referal_users_count(user_id)
                
                stats_text = (
                    f"📊 <b>Global Referral Statistics</b>\n\n"
                    f"👥 Total System Referrals: {total_referrals}\n"
                    f"👤 Your Referrals: {user_referrals}\n"
                    f"🎯 Required for Premium: {REFERAL_COUNT}\n"
                    f"⏰ Premium Duration: {REFERAL_PREMEIUM_TIME}\n\n"
                )
                
                if all_referrals and len(all_referrals) > 0:
                    stats_text += "📋 <b>Recent Activity:</b>\n"
                    for i, ref_user in enumerate(all_referrals[:5]):
                        if isinstance(ref_user, dict):
                            user_info = f"User ID: {ref_user.get('user_id', 'Unknown')}"
                        else:
                            user_info = f"User ID: {ref_user}"
                        stats_text += f"• {user_info}\n"
                    
                    if len(all_referrals) > 5:
                        stats_text += f"... and {len(all_referrals) - 5} more\n"
                else:
                    stats_text += "📋 No referrals found."
            else:
                # Regular users see only their stats
                user_referrals = await get_referal_users_count(user_id)
                
                stats_text = (
                    f"📊 <b>Your Referral Statistics</b>\n\n"
                    f"👤 Your Referrals: {user_referrals}/{REFERAL_COUNT}\n"
                    f"🎯 Required for Premium: {REFERAL_COUNT}\n"
                    f"⏰ Premium Duration: {REFERAL_PREMEIUM_TIME}\n\n"
                )
                
                if user_referrals >= REFERAL_COUNT:
                    stats_text += "🎉 <b>Congratulations!</b> You've earned premium access!\n"
                else:
                    remaining = REFERAL_COUNT - user_referrals
                    stats_text += f"💪 You need {remaining} more referrals to unlock premium!\n"
            
            await processing_msg.edit(stats_text)
            
        except Exception as e:
            logger.error(f"Error getting referral stats: {e}")
            await processing_msg.edit(f"❌ Error fetching stats: <code>{str(e)}</code>")
            
    except Exception as e:
        logger.error(f"Error in referral_stats: {e}")
        await message.reply("❌ An unexpected error occurred.")
