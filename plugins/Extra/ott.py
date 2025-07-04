import requests
import html
from pyrogram import Client, filters
from pyrogram.types import (
    ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton, Message
)

# Clean text from HTML
def clean_text(text):
    if not text:
        return text
    text = html.unescape(text)
    text = text.replace('\u2019', "'").replace('\u2018', "'")
    text = text.replace('\u201c', '"').replace('\u201d', '"')
    return text.strip()

# Fetch data from Binged API
def fetch_ott_data():
    url = "https://www.binged.com/wp-json/binged-api/v1/whats-streaming"
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Referer': 'https://www.binged.com/',
        'Accept': 'application/json'
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        return response.json() if response.status_code == 200 else {}
    except Exception as e:
        print("[OTT] Fetch Error:", e)
        return {}

# Per-user state
ott_sessions = {}

# OTT command trigger
@Client.on_message(filters.command("ott") & filters.private)
async def ott_command_handler(client, message):
    user_id = message.from_user.id
    data = fetch_ott_data()

    if not data:
        await message.reply("⚠️ Could not fetch OTT data. Try again later.")
        return

    ott_sessions[user_id] = {
        "data": data,
        "platform_key": None,
        "page": 0,
        "message_id": None
    }

    keyboard = [[KeyboardButton(clean_text(data[k]["title"]))] for k in data]
    keyboard.append([KeyboardButton("❌ Close OTT")])
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    sent = await message.reply("📺 *Select a Platform:*", reply_markup=markup)
    ott_sessions[user_id]["message_id"] = sent.id

# Handle platform button clicks
@Client.on_message(filters.text & filters.private)
async def ott_platform_choice_handler(client, message):
    user_id = message.from_user.id
    session = ott_sessions.get(user_id)

    if not session:
        return

    if message.text == "❌ Close OTT":
        await message.reply("❌ OTT browsing closed.", reply_markup=ReplyKeyboardRemove())
        del ott_sessions[user_id]
        return

    for k, v in session["data"].items():
        if clean_text(v["title"]) == message.text:
            session["platform_key"] = k
            session["page"] = 0
            await send_ott_movies(client, message, user_id)
            return

# Send a paginated list of movies with inline buttons
async def send_ott_movies(client, message, user_id):
    session = ott_sessions[user_id]
    platform = session["data"][session["platform_key"]]
    movies = platform["movies"]
    page = session["page"]
    start = page * 20
    end = start + 20
    buttons = [
        [InlineKeyboardButton(clean_text(m["title"]), callback_data="noop")]
        for m in movies[start:end]
    ]

    nav = []
    if start > 0:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data="ott_prev"))
    if end < len(movies):
        nav.append(InlineKeyboardButton("➡️ Next", callback_data="ott_next"))
    if nav:
        buttons.append(nav)

    buttons.append([InlineKeyboardButton("🔙 Back to Platforms", callback_data="ott_back")])

    markup = InlineKeyboardMarkup(buttons)
    logo = movies[0].get("platform_logo", "")
    caption = f"🎬 *{platform['title']} Movies*
Select from the list below:"

    try:
        if session["message_id"]:
            await client.delete_messages(message.chat.id, session["message_id"])
        await message.delete()
    except:
        pass

    sent = await client.send_photo(
        message.chat.id, photo=logo, caption=caption, reply_markup=markup
    )
    session["message_id"] = sent.id

# Handle callback queries for pagination
@Client.on_callback_query(filters.regex("^ott_(prev|next|back)$"))
async def handle_ott_navigation(client, cb):
    user_id = cb.from_user.id
    session = ott_sessions.get(user_id)

    if not session:
        await cb.answer("❌ Session expired.", show_alert=True)
        return

    action = cb.data.split("_")[1]
    if action == "prev" and session["page"] > 0:
        session["page"] -= 1
    elif action == "next":
        session["page"] += 1
    elif action == "back":
        session["platform_key"] = None
        session["page"] = 0

        keyboard = [[KeyboardButton(clean_text(session["data"][k]["title"]))] for k in session["data"]]
        keyboard.append([KeyboardButton("❌ Close OTT")])
        markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        try:
            await cb.message.delete()
        except:
            pass

        sent = await client.send_message(cb.message.chat.id, "📺 *Select a Platform:*", reply_markup=markup)
        session["message_id"] = sent.id
        await cb.answer()
        return

    await send_ott_movies(client, cb.message, user_id)
    await cb.answer()

# No-op button handler to avoid invalid callback error
@Client.on_callback_query(filters.regex("^noop$"))
async def noop_cb(client, cb):
    await cb.answer("🎥 Movie button clicked", show_alert=False)
