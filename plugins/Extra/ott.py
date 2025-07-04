import requests
import html
from pyrogram import Client, filters
from pyrogram.types import (
    ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton, Message
)

# Clean HTML/unicode characters
def clean_text(text):
    if not text:
        return text
    text = html.unescape(text)
    text = text.replace('\u2019', "'").replace('\u2018', "'")
    text = text.replace('\u201c', '"').replace('\u201d', '"')
    return text.strip()

# Fetch OTT platform and movie data
def fetch_ott_data():
    url = "https://www.binged.com/wp-json/binged-api/v1/whats-streaming"
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Referer': 'https://www.binged.com/'
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        return response.json() if response.status_code == 200 else {}
    except Exception as e:
        print("Error fetching OTT data:", e)
        return {}

# Store user session data
user_ott_data = {}

# /ott command
@Client.on_message(filters.command("ott"))
async def show_platforms(client, message):
    user_id = message.from_user.id
    data = fetch_ott_data()
    if not data:
        await message.reply("⚠️ Failed to fetch OTT data.")
        return

    user_ott_data[user_id] = {
        "data": data,
        "platform": None,
        "page": 0,
        "message_id": None
    }

    keyboard = [[KeyboardButton(clean_text(data[str(k)]["title"]))] for k in data]
    keyboard.append([KeyboardButton("❌ Close")])
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    sent = await message.reply("📺 **Select a Platform:**", reply_markup=markup)
    user_ott_data[user_id]["message_id"] = sent.id

# Handle platform name as text message (keyboard)
@Client.on_message(filters.text & ~filters.command("ott"))
async def handle_platform_choice(client, message: Message):
    user_id = message.from_user.id
    text = message.text.strip()

    if text == "❌ Close":
        await message.reply("❌ Closed", reply_markup=ReplyKeyboardRemove())
        return

    if user_id not in user_ott_data:
        return

    session = user_ott_data[user_id]
    data = session["data"]

    # Match platform name
    for k, v in data.items():
        if clean_text(v["title"]) == text:
            session["platform"] = k
            session["page"] = 0
            await send_movie_page(client, message, user_id)
            return

# Send inline movie buttons (paginated) with platform image
async def send_movie_page(client, message, user_id):
    session = user_ott_data[user_id]
    platform_key = session["platform"]
    page = session["page"]
    data = session["data"]

    platform_data = data[platform_key]
    movies = platform_data["movies"]
    platform_name = platform_data["title"]
    platform_logo = platform_data["movies"][0].get("platform_logo", "")
    
    per_page = 20
    start = page * per_page
    end = start + per_page
    current_movies = movies[start:end]

    # Inline buttons
    buttons = []
    for movie in current_movies:
        title = clean_text(movie["title"])
        buttons.append([InlineKeyboardButton(title, callback_data=f"ignore")])

    # Navigation
    nav = []
    if start > 0:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data="prev_ott"))
    if end < len(movies):
        nav.append(InlineKeyboardButton("➡️ Next", callback_data="next_ott"))
    if nav:
        buttons.append(nav)
    
    buttons.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="back_ott")])

    markup = InlineKeyboardMarkup(buttons)

    # Delete previous
    old_msg_id = session.get("message_id")
    try:
        if old_msg_id:
            await client.delete_messages(message.chat.id, old_msg_id)
        await message.delete()
    except:
        pass

    # Send new message with platform image
    sent = await client.send_photo(
        chat_id=message.chat.id,
        photo=platform_logo,
        caption=f"🎬 **{platform_name} Movies**\nSelect from the titles below:",
        reply_markup=markup
    )
    session["message_id"] = sent.id

# Handle callback navigation
@Client.on_callback_query(filters.regex("^(next_ott|prev_ott|back_ott)$"))
async def navigate_ott_pages(client, callback_query):
    user_id = callback_query.from_user.id
    session = user_ott_data.get(user_id)

    if not session:
        await callback_query.answer("Session expired", show_alert=True)
        return

    if callback_query.data == "next_ott":
        session["page"] += 1
        await send_movie_page(client, callback_query.message, user_id)
    elif callback_query.data == "prev_ott" and session["page"] > 0:
        session["page"] -= 1
        await send_movie_page(client, callback_query.message, user_id)
    elif callback_query.data == "back_ott":
        session["platform"] = None
        session["page"] = 0
        keyboard = [[KeyboardButton(clean_text(session["data"][k]["title"]))] for k in session["data"]]
        keyboard.append([KeyboardButton("❌ Close")])
        markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        try:
            if session["message_id"]:
                await client.delete_messages(callback_query.message.chat.id, session["message_id"])
        except:
            pass

        sent = await client.send_message(
            chat_id=callback_query.message.chat.id,
            text="📺 **Select a Platform:**",
            reply_markup=markup
        )
        session["message_id"] = sent.id

    await callback_query.answer()
