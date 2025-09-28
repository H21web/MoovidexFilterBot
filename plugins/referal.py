from urllib.parse import quote_plus
from database.users_chats_db import db, delete_all_referal_users, get_referal_users_count, get_referal_all_users, referal_add_user
from pyrogram import Client
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

async def invite_handler(client: Client, message: Message):
    bot_username = (await client.get_me()).username
    user_id = message.from_user.id
    referral_link = f"https://t.me/{bot_username}?start=MVDEX-{user_id}"
    num_referrals = await get_referal_users_count(user_id)

    # Simple share text
    share_text = quote_plus("🎬 Amazing movie bot! Join me and search unlimited movies!")
    share_url = f"https://t.me/share/url?url={referral_link}&text={share_text}"

    # Simple progress visualization
    remaining = max(0, REFERAL_COUNT - num_referrals)
    progress = "🟢" * min(num_referrals, REFERAL_COUNT) + "⚪" * remaining

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 Share Link", url=share_url)],
        [InlineKeyboardButton("📋 Copy Link", callback_data=f"copy_{user_id}")],
        [InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh_{user_id}")]
    ])
    
    # Simple status message
    if num_referrals >= REFERAL_COUNT:
        status = "🎉 Awesome! You can search unlimited movies!"
    else:
        status = f"📢 Invite {remaining} friends to unlock unlimited movie search!"
    
    await message.reply(
        f"<b>🚀 Invite Friends</b>\n\n"
        f"{status}\n\n"
        f"📊 Friends joined: {num_referrals}/{REFERAL_COUNT}\n"
        f"{progress[:10]}\n\n"
        f"🔗 Your link:\n<code>{referral_link}</code>\n\n"
        f"💡 <b>How it works:</b>\n"
        f"• Share your link with friends\n"
        f"• They join the bot using your link\n"
        f"• You get unlimited movie searches!\n\n"
        f"<i>Simple and fair! 😊</i>",
        reply_markup=buttons
    )

async def referral_required_message(client: Client, message: Message):
    """Simple message when user needs more referrals"""
    bot_username = (await client.get_me()).username
    user_id = message.from_user.id
    referral_link = f"https://t.me/{bot_username}?start=MVDEX-{user_id}"
    num_referrals = await get_referal_users_count(user_id)
    remaining = REFERAL_COUNT - num_referrals
    
    # Simple share text
    share_text = quote_plus("🎬 Found an amazing movie bot! Join me!")
    share_url = f"https://t.me/share/url?url={referral_link}&text={share_text}"
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 Share with Friends", url=share_url)],
        [InlineKeyboardButton("🔄 Check Status", callback_data=f"refresh_{user_id}")]
    ])
    
    await message.reply(
        f"🎬 <b>Hey! Quick favor needed</b>\n\n"
        f"To keep searching movies, just invite <b>{remaining} friends</b> to join!\n\n"
        f"📊 Progress: {num_referrals}/{REFERAL_COUNT} friends\n\n"
        f"🔗 <b>Your magic link:</b>\n<code>{referral_link}</code>\n\n"
        f"💬 <b>Just tell them:</b>\n"
        f"<i>\"Found a cool movie bot! Check it out: {referral_link}\"</i>\n\n"
        f"✨ <b>Once {remaining} friends join = Unlimited searches!</b>",
        reply_markup=buttons
    )

async def copy_link_callback(client: Client, callback_query: CallbackQuery):
    """Handle copy link button - Fixed version"""
    try:
        # Extract user_id from callback data
        callback_data = callback_query.data
        user_id = int(callback_data.split('_')[1])
        
        bot_username = (await client.get_me()).username
        referral_link = f"https://t.me/{bot_username}?start=MVDEX-{user_id}"
        
        await callback_query.answer(
            f"📋 Link ready to share!\n{referral_link}",
            show_alert=True
        )
    except Exception as e:
        await callback_query.answer("❌ Something went wrong. Try again!", show_alert=True)

async def refresh_referrals_callback(client: Client, callback_query: CallbackQuery):
    """Handle refresh/check referrals button - Fixed version"""
    try:
        # Extract user_id from callback data
        callback_data = callback_query.data
        user_id = int(callback_data.split('_')[1])
        
        num_referrals = await get_referal_users_count(user_id)
        remaining = max(0, REFERAL_COUNT - num_referrals)
        
        if num_referrals >= REFERAL_COUNT:
            message = "🎉 Perfect! You can now search unlimited movies!"
        else:
            message = f"📊 {num_referrals}/{REFERAL_COUNT} friends joined\n⏳ Need {remaining} more for unlimited search!"
        
        await callback_query.answer(message, show_alert=True)
        
        # Optionally update the message with new stats
        if callback_query.message:
            await update_invite_message(client, callback_query.message, user_id)
            
    except Exception as e:
        await callback_query.answer("❌ Can't check right now. Try again!", show_alert=True)

async def update_invite_message(client: Client, message: Message, user_id: int):
    """Update the invite message with current stats"""
    try:
        bot_username = (await client.get_me()).username
        referral_link = f"https://t.me/{bot_username}?start=MVDEX-{user_id}"
        num_referrals = await get_referal_users_count(user_id)
        remaining = max(0, REFERAL_COUNT - num_referrals)
        progress = "🟢" * min(num_referrals, REFERAL_COUNT) + "⚪" * remaining
        
        share_text = quote_plus("🎬 Amazing movie bot! Join me and search unlimited movies!")
        share_url = f"https://t.me/share/url?url={referral_link}&text={share_text}"
        
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("📤 Share Link", url=share_url)],
            [InlineKeyboardButton("📋 Copy Link", callback_data=f"copy_{user_id}")],
            [InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh_{user_id}")]
        ])
        
        if num_referrals >= REFERAL_COUNT:
            status = "🎉 Awesome! You can search unlimited movies!"
        else:
            status = f"📢 Invite {remaining} friends to unlock unlimited movie search!"
        
        await message.edit_text(
            f"<b>🚀 Invite Friends</b>\n\n"
            f"{status}\n\n"
            f"📊 Friends joined: {num_referrals}/{REFERAL_COUNT}\n"
            f"{progress[:10]}\n\n"
            f"🔗 Your link:\n<code>{referral_link}</code>\n\n"
            f"💡 <b>How it works:</b>\n"
            f"• Share your link with friends\n"
            f"• They join the bot using your link\n"
            f"• You get unlimited movie searches!\n\n"
            f"<i>Simple and fair! 😊</i>",
            reply_markup=buttons
        )
    except:
        pass  # Ignore if message can't be updated

# Callback handler registration helper
def register_referral_callbacks(app: Client):
    """Register all callback handlers"""
    
    @app.on_callback_query()
    async def handle_callbacks(client: Client, callback_query: CallbackQuery):
        data = callback_query.data
        
        if data.startswith("copy_"):
            await copy_link_callback(client, callback_query)
        elif data.startswith("refresh_"):
            await refresh_referrals_callback(client, callback_query)

# Usage:
# 1. Call register_referral_callbacks(app) when starting your bot
# 2. Use invite_handler() for invite command
# 3. Use referral_required_message() when user hits limits
