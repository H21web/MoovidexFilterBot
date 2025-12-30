import datetime
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.users_chats_db import db
from utils import get_seconds
from info import *

async def process_referral(client, message, referrer_id):
    """
    Process a new referral:
    1. Add user to referrer's list.
    2. Notify referrer.
    3. Grant premium to referrer if eligible.
    4. Grant welcome bonus (10 free searches) to the new user.
    """
    user_id = message.from_user.id
    
    # Check if self-referral
    if user_id == referrer_id:
        return await message.reply("<b>🤦‍♂️ You cannot refer yourself!</b>")

    # Add to Database
    is_new = await db.referal_add_user(referrer_id, user_id)
    
    if is_new:
        # 1. Notify New User & Grant Bonus
        # Give 10 bonus searches as a welcome gift
        await db.add_bonus_searches(user_id, 10)
        
        await message.reply(
            f"<b>🎉 Welcome to {temp.U_NAME}!</b>\n\n"
            f"You have joined via referral link of ID: <code>{referrer_id}</code>\n"
            f"🎁 <b>Welcome Bonus:</b> You got <b>10 EXTRA Free Searches</b> for today!\n\n"
            f"<i>Send /start again to begin searching movies!</i>"
        )

        # 2. Notify Referrer
        num_referrals = await db.get_referal_users_count(referrer_id)
        
        # Check if referrer exists (to send message)
        try:
             await client.send_message(
                chat_id=referrer_id,
                text=(
                    f"🔔 <b>New Referral Joined!</b> 🔔\n\n"
                    f"👤 <b>User:</b> {message.from_user.mention}\n"
                    f"🆔 <b>ID:</b> <code>{message.from_user.id}</code>\n\n"
                    f"📊 <b>Total Referrals:</b> {num_referrals}/{REFERAL_COUNT}\n\n"
                    f"<i>Keep referring to unlock premium access!</i>"
                )
            )
        except Exception:
            pass # Referrer might have blocked bot

        # 3. Grant Premium if eligible
        if num_referrals >= REFERAL_COUNT:
            time = REFERAL_PREMEIUM_TIME       
            seconds = await get_seconds(time)
            if seconds > 0:
                expiry_time = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
                user_data = {"id": referrer_id, "expiry_time": expiry_time} 
                await db.update_user(user_data)
                
                # Reset referral count
                await db.delete_all_referal_users(referrer_id)
                
                try:
                    await client.send_message(
                        chat_id=referrer_id,
                        text=(
                            f"🎉 <b>CONGRATULATIONS!</b> 🎉\n\n"
                            f"<b>You have successfully completed the referral requirement!</b> 🚀\n\n"
                            f"✅ <b>Reward:</b> 3 Months Unlimited Access\n"
                            f"⏳ <b>Valid Until:</b> {expiry_time.strftime('%d %B %Y')}\n\n"
                            f"<i>Enjoy your premium access to movies and series!</i> 🍿🎬"
                        )
                    )
                except Exception:
                    pass
    else:
        await message.reply("<b>You have already been referred or used this link!</b>")
