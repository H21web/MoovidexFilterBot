from database.users_chats_db import db, delete_all_referal_users, get_referal_users_count, get_referal_all_users, referal_add_user
from pyrogram import Client
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from info import REFERAL_COUNT, REFERAL_PREMEIUM_TIME

async def invite_handler(client: Client, message: Message):
    bot_username = (await client.get_me()).username
    user_id = message.from_user.id
    referral_link = f"https://t.me/{bot_username}?start=MVDEX-{user_id}"
    num_referrals = await get_referal_users_count(user_id)
    
    # Calculate progress
    progress_percentage = (num_referrals / REFERAL_COUNT) * 100
    progress_bar = "🟢" * int(progress_percentage // 10) + "⚪" * (10 - int(progress_percentage // 10))
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 Share with Friends", url=f"https://t.me/share/url?url={referral_link}&text=🎬 Join me on this amazing movie bot! Get premium access and search unlimited movies!")],
        [InlineKeyboardButton("📋 Copy Link", callback_data=f"copy_link_{user_id}")],
        [InlineKeyboardButton("👥 My Referrals", callback_data=f"my_referrals_{user_id}")]
    ])
    
    # Different messages based on referral progress
    if num_referrals >= REFERAL_COUNT:
        status_emoji = "✅"
        status_text = "Congratulations! You've unlocked Premium!"
    elif num_referrals >= REFERAL_COUNT * 0.8:
        status_emoji = "🔥"
        status_text = f"Almost there! Just {REFERAL_COUNT - num_referrals} more friends needed!"
    elif num_referrals >= REFERAL_COUNT * 0.5:
        status_emoji = "⚡"
        status_text = f"Great progress! {REFERAL_COUNT - num_referrals} more invites to go!"
    else:
        status_emoji = "🚀"
        status_text = f"Start inviting! {REFERAL_COUNT - num_referrals} friends needed for premium!"
    
    await message.reply(
        f"<b>{status_emoji} Invite Friends & Get Premium!</b>\n\n"
        f"📊 Progress: {num_referrals}/{REFERAL_COUNT}\n"
        f"{progress_bar} {progress_percentage:.0f}%\n\n"
        f"🎁 <b>Reward:</b> Premium for {REFERAL_PREMEIUM_TIME}\n"
        f"🔗 <b>Your Link:</b> <code>{referral_link}</code>\n\n"
        f"<i>{status_text}</i>\n\n"
        "💡 <b>Why invite friends?</b>\n"
        "• 🎬 Unlimited movie searches\n"
        "• 🚀 Faster responses\n"
        "• 🔥 Premium features access\n"
        "• 📱 No daily limits",
        reply_markup=buttons
    )

async def referral_required_message(client: Client, message: Message):
    """Show this when user needs to refer friends to continue"""
    bot_username = (await client.get_me()).username
    user_id = message.from_user.id
    referral_link = f"https://t.me/{bot_username}?start=MVDEX-{user_id}"
    num_referrals = await get_referal_users_count(user_id)
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 Invite Friends Now", url=f"https://t.me/share/url?url={referral_link}&text=🎬 Join me on this amazing movie bot!")],
        [InlineKeyboardButton("🔄 Check My Progress", callback_data=f"check_referrals_{user_id}")]
    ])
    
    await message.reply(
        "🔒 <b>Oops! You've reached your daily limit</b>\n\n"
        f"📊 Your Referrals: {num_referrals}/{REFERAL_COUNT}\n"
        f"⏳ Need: {REFERAL_COUNT - num_referrals} more friends\n\n"
        "🎯 <b>To continue searching movies:</b>\n"
        f"• Invite {REFERAL_COUNT - num_referrals} friends using your link\n"
        f"• Get Premium for {REFERAL_PREMEIUM_TIME}\n"
        "• Enjoy unlimited searches! 🎬\n\n"
        f"🔗 <b>Share this link:</b>\n<code>{referral_link}</code>\n\n"
        "💬 <b>Tell your friends:</b>\n"
        "<i>\"Hey! I found this amazing movie bot that has everything! Join me and let's watch movies together! 🍿\"</i>",
        reply_markup=buttons
    )

async def copy_link_callback(client: Client, callback_query):
    """Handle copy link button press"""
    user_id = callback_query.from_user.id
    bot_username = (await client.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start=MVDEX-{user_id}"
    
    await callback_query.answer(
        f"📋 Link copied!\n{referral_link}",
        show_alert=True
    )

async def check_referrals_callback(client: Client, callback_query):
    """Handle check referrals button press"""
    user_id = callback_query.from_user.id
    num_referrals = await get_referal_users_count(user_id)
    
    if num_referrals >= REFERAL_COUNT:
        message = f"🎉 Congratulations! You have {num_referrals} referrals and Premium access!"
    else:
        remaining = REFERAL_COUNT - num_referrals
        message = f"📊 Current: {num_referrals}/{REFERAL_COUNT}\n⏳ Need {remaining} more friends for Premium!"
    
    await callback_query.answer(message, show_alert=True)

# Usage examples:
# Call invite_handler() when user clicks "Invite Friends" button
# Call referral_required_message() when user hits daily limit and needs to refer
# Add copy_link_callback and check_referrals_callback to your callback handlers
