from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

# Global Maintenance State
MAINTENANCE_MODE = {
    "is_on": False,
    "reason": "No reason provided."
}

# /maintenance command (admin only)
@Client.on_message(filters.command("maintenance") & filters.user(ADMIN_USERS))
async def maintenance_cmd(client, message: Message):
    btns = [
        [InlineKeyboardButton("🟢 Turn ON", callback_data="maint_on"),
         InlineKeyboardButton("🔴 Turn OFF", callback_data="maint_off")],
        [InlineKeyboardButton("📝 Apply Reason", callback_data="maint_reason")]
    ]
    await message.reply(
        f"🛠️ <b>Maintenance Mode Settings</b>\n\nCurrent: {'ON' if MAINTENANCE_MODE['is_on'] else 'OFF'}\nReason: {MAINTENANCE_MODE['reason']}",
        reply_markup=InlineKeyboardMarkup(btns)
    )

# Handle callback queries
@Client.on_callback_query(filters.regex("maint_"))
async def maintenance_callback(client, query: CallbackQuery):
    user_id = query.from_user.id
    if user_id not in ADMIN_USERS:
        return await query.answer("You're not allowed.", show_alert=True)

    data = query.data
    if data == "maint_on":
        if not MAINTENANCE_MODE["reason"]:
            return await query.answer("Please apply a reason first.", show_alert=True)
        MAINTENANCE_MODE["is_on"] = True
        await query.edit_message_text(f"✅ Maintenance mode is now <b>ON</b>\nReason: {MAINTENANCE_MODE['reason']}")

    elif data == "maint_off":
        MAINTENANCE_MODE["is_on"] = False
        MAINTENANCE_MODE["reason"] = ""
        await query.edit_message_text("❎ Maintenance mode is now <b>OFF</b>")

    elif data == "maint_reason":
        await query.message.reply("📝 Send me the maintenance reason (in one message).")
        return

# Catch the reason message
@Client.on_message(filters.user(ADMIN_USERS) & filters.text & filters.private)
async def handle_reason(client, message: Message):
    if MAINTENANCE_MODE["is_on"]:
        return  # Do not accept during active maintenance
    if message.reply_to_message and "Send me the maintenance reason" in message.reply_to_message.text:
        MAINTENANCE_MODE["reason"] = message.text
        await message.reply("✅ Reason updated. You can now enable Maintenance Mode.")
