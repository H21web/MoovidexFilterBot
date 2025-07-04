import requests
import html
import asyncio
from pyrogram import Client, filters
from pyrogram.types import ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton

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

# Store data by user
user_ott_data = {}

# /ott command
@Client.on_message(filters.command("ott"))
async def show_ott_platforms(client, message):
    data = fetch_ott_data()
    if not data:
        await message.reply_text("⚠️ Failed to fetch OTT data.")
        return

    user_id = message.from_user.id
    user_ott_data[user_id] = {"data": data, "page": 0, "platform": None, "message_id": None}

    keyboard = [[KeyboardButton(clean_text(data[str(k)]["title"]))] for k in data]
    keyboard.append([KeyboardButton("❌ Close")])
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    sent = await message.reply("📺 **Select a Platform:**", reply_markup=reply_markup)
    user_ott_data[user_id]["message_id"] = sent.id

# Show movie titles on platform selection
@Client.on_message(filters.text & ~filters.command(["ott"]))
async def handle_platform_selection(client, message):
    if not message.from_user:
        return  # Handles anonymous admins or system messages

    user_id = message.from_user.id
    if user_id not in user_ott_data:
        return

    text = message.text.strip()
    if text == "❌ Close":
        await message.reply("❌ Closed", reply_markup=ReplyKeyboardRemove())
        return

    user_info = user_ott_data[user_id]
    for k, v in user_info["data"].items():
        if clean_text(v["title"]) == text:
            user_info["platform"] = k
            user_info["page"] = 0
            await show_movie_titles(client, message, user_id)
            return

    if text in ["➡️ Next", "⬅️ Prev", "🔙 Back to Menu"]:
        await navigate_movies(client, message)

# Show paginated movies
async def show_movie_titles(client, message, user_id):
    info = user_ott_data[user_id]
    data = info["data"]
    platform_key = info["platform"]
    page = info["page"]

    movies = data[platform_key]["movies"]
    page_size = 20
    start, end = page * page_size, (page + 1) * page_size
    current_movies = movies[start:end]

    if not current_movies:
        await message.reply("⚠️ No movies found.")
        return

    keyboard = []
    row = []
    for movie in current_movies:
        title = clean_text(movie.get("title", "Untitled"))
        row.append(KeyboardButton(title))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    nav_buttons = []
    if start > 0:
        nav_buttons.append(KeyboardButton("⬅️ Prev"))
    if end < len(movies):
        nav_buttons.append(KeyboardButton("➡️ Next"))
    if nav_buttons:
        keyboard.append(nav_buttons)

    keyboard.append([KeyboardButton("🔙 Back to Menu")])
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    # Cleanup old message
    old_id = info.get("message_id")
    try:
        if old_id:
            await client.delete_messages(message.chat.id, old_id)
        await message.delete()
    except:
        pass

    sent = await client.send_message(message.chat.id, f"🎞️ **{data[platform_key]['title']} Movies:**", reply_markup=reply_markup)
    info["message_id"] = sent.id

# Navigate pages
async def navigate_movies(client, message):
    user_id = message.from_user.id
    info = user_ott_data[user_id]

    if message.text == "➡️ Next":
        info["page"] += 1
    elif message.text == "⬅️ Prev" and info["page"] > 0:
        info["page"] -= 1
    elif message.text == "🔙 Back to Menu":
        info["platform"] = None
        info["page"] = 0
        keyboard = [[KeyboardButton(clean_text(info["data"][k]["title"]))] for k in info["data"]]
        keyboard.append([KeyboardButton("❌ Close")])
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        try:
            await message.delete()
            if info["message_id"]:
                await client.delete_messages(message.chat.id, info["message_id"])
        except:
            pass
        sent = await client.send_message(message.chat.id, "📺 **Select a Platform:**", reply_markup=reply_markup)
        info["message_id"] = sent.id
        return

    await show_movie_titles(client, message, user_id)
