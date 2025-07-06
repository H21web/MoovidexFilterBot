import re
from pyrogram import Client, filters
from pyrogram.types import ReplyKeyboardMarkup
from database.config_db import mdb

# most search commands
@Client.on_message(filters.command('most'))
async def most(client, message):

    def is_alphanumeric(string):
        return bool(re.match('^[a-zA-Z0-9 ]*$', string))
    
    try:
        limit = int(message.command[1])
    except (IndexError, ValueError):
        limit = 20

    top_messages = await mdb.get_top_messages(limit)

    # Use a set to ensure unique messages (case sensitive).
    seen_messages = set()
    truncated_messages = []

    for msg in top_messages:
        # Check if message already exists in the set (case sensitive)
        if msg.lower() not in seen_messages and is_alphanumeric(msg):
            seen_messages.add(msg.lower())
            
            if len(msg) > 35:
                truncated_messages.append(msg[:35 - 3])
            else:
                truncated_messages.append(msg)

    keyboard = []
    for i in range(0, len(truncated_messages), 2):
        row = truncated_messages[i:i+2]
        keyboard.append(row)
    
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True, placeholder="Most searches of the day")
    m=await message.reply_text("Please wait...")
    await m.edit_text("Fetching Most Searches.")
    await m.delete()
    await message.reply_text(f"<b>Here is the most searched list 👇</b>", reply_markup=reply_markup)

    
@Client.on_message(filters.command('mostlist'))
async def trendlist(client, message):
    def is_alphanumeric(string):
        return bool(re.match('^[a-zA-Z0-9 ]*$', string))

    # Set the limit to the default if no argument is provided
    limit = 31

    # Check if an argument is provided and if it's a valid number
    if len(message.command) > 1:
        try:
            limit = int(message.command[1])
        except ValueError:
            await message.reply_text("Invalid number format.\nPlease provide a valid number after the /trendlist command.")
            return  # Exit the function if the argument is not a valid integer

    try:
        top_messages = await mdb.get_top_messages(limit)
    except Exception as e:
        await message.reply_text(f"Error retrieving messages: {str(e)}")
        return  # Exit the function if there is an error retrieving messages

    if not top_messages:
        await message.reply_text("No most messages found.")
        return  # Exit the function if no messages are found

    seen_messages = set()
    truncated_messages = []

    for msg in top_messages:
        if msg.lower() not in seen_messages and is_alphanumeric(msg):
            seen_messages.add(msg.lower())
            
            # Add an ellipsis to indicate the message has been truncated
            truncated_messages.append(msg[:32] + '...' if len(msg) > 35 else msg)

    if not truncated_messages:
        await message.reply_text("No valid most messages found.")
        return  # Exit the function if no valid messages are found

    # Create a formatted text list
    formatted_list = "\n".join([f"{i+1}. <b>{msg}</b>" for i, msg in enumerate(truncated_messages)])

    # Append the additional message at the end
    additional_message = "𝑨𝒍𝒍 𝒕𝒉𝒆 𝒓𝒆𝒔𝒖𝒍𝒕𝒔 𝒂𝒃𝒐𝒗𝒆 𝒄𝒐𝒎𝒆 𝒇𝒓𝒐𝒎 𝒘𝒉𝒂𝒕 𝒖𝒔𝒆𝒓𝒔 𝒉𝒂𝒗𝒆 𝒔𝒆𝒂𝒓𝒄𝒉𝒆𝒅 𝒇𝒐𝒓. 𝑻𝒉𝒆𝒚'𝒓𝒆 𝒔𝒉𝒐𝒘𝒏 𝒕𝒐 𝒚𝒐𝒖 𝒆𝒙𝒂𝒄𝒕𝒍𝒚 𝒂𝒔 𝒕𝒉𝒆𝒚 𝒘𝒆𝒓𝒆 𝒔𝒆𝒂𝒓𝒄𝒉𝒆𝒅, 𝒘𝒊𝒕𝒉𝒐𝒖𝒕 𝒂𝒏𝒚 𝒄𝒉𝒂𝒏𝒈𝒆𝒔 𝒃𝒚 𝒕𝒉𝒆 𝒐𝒘𝒏𝒆𝒓."
    formatted_list += f"\n\n{additional_message}"

    reply_text = f"<b><u>Top {len(truncated_messages)} Most Searches List:</u></b>\n\n{formatted_list}"
    
    await message.reply_text(reply_text)
