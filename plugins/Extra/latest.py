import aiohttp
import html
import asyncio
from pyrogram import Client, filters
from pyrogram.types import ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton

# Clean text
def clean_text(text):
    if not text:
        return text
    text = html.unescape(text)
    text = text.replace('\u2019', "'").replace('\u2018', "'")
    text = text.replace('\u201c', '"').replace('\u201d', '"')
    text = text.replace('\u2013', '-').replace('\u2014', '-')
    text = text.replace('\u2026', '...')
    return text.strip()

# Fetch movie page
async def fetch_movies_page(page=1):
    url = f"https://www.binged.com/wp-json/binged-api/v1/movies?page={page}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Referer': 'https://www.binged.com/',
        'Accept': 'application/json'
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=10) as response:
                if response.status != 200:
                     return [], 1
                data = await response.json()
                return data.get("data", []), data.get("pagination", {}).get("total_pages", 1)
    except Exception as e:
        print("Error while fetching page:", e)
        return [], 1

# Session store
user_pages = {}  # user_id: {"page": 1, "total_pages": 1, "movies": [], "message_id": id}

# /latest command
@Client.on_message(filters.command("latest"))
async def latest_movies_command(client, message):
    user_id = message.from_user.id
    page = 1

    movies, total_pages = await fetch_movies_page(page)
    if not movies:
        await message.reply_text("⚠️ Failed to fetch movies.")
        return

    user_pages[user_id] = {
        "page": page,
        "total_pages": total_pages,
        "movies": movies,
        "message_id": None
    }

    sent = await send_movies_page(client, message.chat.id, user_id)
    user_pages[user_id]["message_id"] = sent.id

# Send movies
async def send_movies_page(client, chat_id, user_id):
    movies = user_pages[user_id]["movies"]
    titles = [clean_text(movie.get("title", "Untitled")) for movie in movies]

    keyboard = []
    row = []
    for title in titles:
        row.append(KeyboardButton(title))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    # Navigation buttons
    page = user_pages[user_id]["page"]
    total_pages = user_pages[user_id]["total_pages"]
    nav_row = []
    if page > 1:
        nav_row.append(KeyboardButton("⬅️ Prev"))
    if page < total_pages:
        nav_row.append(KeyboardButton("➡️ Next"))
    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([KeyboardButton("❌ Close")])
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    return await client.send_message(chat_id, f"🎬 **Latest Streaming Movies:**\n📄 Page {page}", reply_markup=reply_markup)

# Pagination
@Client.on_message(filters.text & filters.regex("^(⬅️ Prev|➡️ Next)$"))
async def paginate_movies(client, message):
    user_id = message.from_user.id
    if user_id not in user_pages:
        return

    current = user_pages[user_id]["page"]
    total = user_pages[user_id]["total_pages"]

    if message.text == "➡️ Next" and current < total:
        new_page = current + 1
    elif message.text == "⬅️ Prev" and current > 1:
        new_page = current - 1
    else:
        return

    movies, _ = await fetch_movies_page(new_page)
    if not movies:
        await message.reply_text("⚠️ Failed to fetch movies.")
        return

    user_pages[user_id]["page"] = new_page
    user_pages[user_id]["movies"] = movies

    # Delete user message (button press)
    try:
        await message.delete()
    except:
        pass

    # Also delete old bot message
    old_msg_id = user_pages[user_id]["message_id"]
    if old_msg_id:
        try:
            await client.delete_messages(message.chat.id, old_msg_id)
        except:
            pass

    sent = await send_movies_page(client, message.chat.id, user_id)
    user_pages[user_id]["message_id"] = sent.id

# Close keyboard
@Client.on_message(filters.text & filters.regex("^❌ Close$"))
async def close_keyboard(client, message):
    await message.delete()
    try:
        sent = await client.send_message(
            message.chat.id, "❌ Closed", reply_markup=ReplyKeyboardRemove())
        await asyncio.sleep(10)
        await client.delete_messages(message.chat.id, sent.id)
    except:
        pass
