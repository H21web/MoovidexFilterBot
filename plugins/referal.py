from urllib.parse import quote_plus 
from database.users_chats_db import get_referal_users_count
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from info import REFERAL_COUNT

# --- Invite handler (command) ---
async def invite_handler(client: Client, message: Message):
    user_id = message.from_user.id
    await send_invite_message(client, message, user_id)

# --- Show invite message when referral required ---
async def referral_required_message(client: Client, message: Message):
    user_id = message.from_user.id
    await send_invite_message(client, message, user_id)

# --- Generate invite message content ---
async def generate_invite_content(client: Client, user_id: int):
    bot_username = (await client.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start=MVDEX-{user_id}"
    num_referrals = await get_referal_users_count(user_id)
    remaining = max(0, REFERAL_COUNT - num_referrals)
    progress = "🟢" * min(num_referrals, REFERAL_COUNT) + "⚪" * remaining
    
    share_text = quote_plus("🎬 Amazing movie bot! Join me and search unlimited movies!")
    share_url = f"https://t.me/share/url?url={referral_link}&text={share_text}"
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 Share Link", url=share_url)],
        [InlineKeyboardButton("🔄 Refresh", callback_data=f"ref_refresh_{user_id}")]
    ])
    
    if num_referrals >= REFERAL_COUNT:
        status = "🎉 Awesome! You can search unlimited movies!"
    else:
        status = f"📢 Invite {remaining} friends to unlock unlimited movie search!"
    
    text = (
        f"<b>🚀 Invite Friends</b>\n\n"
        f"{status}\n\n"
        f"📊 Friends joined: {num_referrals}/{REFERAL_COUNT}\n"
        f"{progress[:10]}\n\n"
        f"🔗 Your link:\n<code>{referral_link}</code>\n\n"
        f"💡 <b>How it works:</b>\n"
        f"• Share your link with friends\n"
        f"• They join the bot using your link\n"
        f"• You get unlimited movie searches!\n\n"
        f"<i>Simple and fair! 😊</i>"
    )
    
    return text, buttons

# --- Send new invite message ---
async def send_invite_message(client: Client, message: Message, user_id: int):
    try:
        text, buttons = await generate_invite_content(client, user_id)
        await message.reply(text, reply_markup=buttons)
    except Exception as e:
        print(f"Error sending invite message: {e}")
        await message.reply("❌ Something went wrong. Please try again later.")

# --- Update existing invite message ---
async def update_invite_message(client: Client, callback_message: Message, user_id: int):
    try:
        text, buttons = await generate_invite_content(client, user_id)
        await callback_message.edit_text(text, reply_markup=buttons)
    except Exception as e:
        print(f"Error updating invite message: {e}")
        raise

# --- Refresh callback handler ---
@Client.on_callback_query(filters.regex("^ref_refresh_"))
async def handle_refresh_callback(client: Client, callback_query: CallbackQuery):
    try:
        # Extract user_id from callback data
        user_id_from_callback = int(callback_query.data.split('_')[2])
        requesting_user_id = callback_query.from_user.id
        
        # Security check: only the owner can refresh their own stats
        if user_id_from_callback != requesting_user_id:
            await callback_query.answer("❌ You can only refresh your own referrals!", show_alert=True)
            return
        
        # Update the message
        await update_invite_message(client, callback_query.message, requesting_user_id)
        await callback_query.answer("✅ Refreshed!", show_alert=False)
        
    except IndexError:
        await callback_query.answer("❌ Invalid refresh request!", show_alert=True)
    except ValueError:
        await callback_query.answer("❌ Invalid user ID!", show_alert=True)
    except Exception as e:
        print(f"Error in refresh callback: {e}")
        await callback_query.answer("❌ Can't refresh right now. Try again!", show_alert=True)
