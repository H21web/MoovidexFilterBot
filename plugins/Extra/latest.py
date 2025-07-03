import requests
import html
from pyrogram import Client, filters
from pyrogram.types import ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton

# Clean HTML/unicode characters
def clean_text(text):
    if not text:
        return text
    text = html.unescape(text)
    text = text.replace('\u2019', "'").replace('\u2018', "'")
    text = text.replace('\u201c', '"').replace('\u201d', '"')
    text = text.replace('\u2013', '-').replace('\u2014', '-')
    text = text.replace('\u2026', '...')
    return text.strip()

# Fetch all movies, keep all streaming releases
def fetch_latest_movies():
    url = "https://www.binged.com/wp-json/binged-api/v1/movies?mode=streaming-week"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.121 Safari/537.36',
        'Referer': 'https://www.binged.com/'
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return [m for m in data.get('data', []) if m.get("mode") == "Streaming"]
    except Exception as e:
        print("Error fetching latest movies:", e)
    return []

# Store paginated movie data per user
user_pages = {}

# /latest command handler
@Client.on_message(filters.command("latest"))
async def latest_movies_command(client, message):
    movies_data = fetch_latest_movies()
    if not movies_data:
        await message.reply_text("⚠️ No latest movies found or failed to fetch.")
        return

    titles = [clean_text(movie.get("title", "Untitled")) for movie in movies_data]

    user_id = message.from_user.id
    user_pages[user_id] = {"titles": titles, "page": 0}

    await send_movies_page(client, message.chat.id, user_id, page=0)

# Send one paginated page of titles
async def send_movies_page(client, chat_id, user_id, page):
    page_size = 20  # 2-column layout = 10 rows
    titles = user_pages[user_id]["titles"]

    if titles:
        latest_title = titles[0]         # First from API (latest)
        rest_titles = titles[1:]         # Remaining
        display_titles = rest_titles + [latest_title]  # Move latest to last
    else:
        display_titles = []

    start = page * page_size
    end = start + page_size
    current_titles = display_titles[start:end]

    keyboard = []
    row = []
    for title in current_titles:
        row.append(KeyboardButton(title))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    nav_buttons = []
    if page > 0:
        nav_buttons.append(KeyboardButton("⬅️ Prev"))
    if end < len(display_titles):
        nav_buttons.append(KeyboardButton("➡️ Next"))
    if nav_buttons:
        keyboard.append(nav_buttons)

    keyboard.append([KeyboardButton("❌ Close")])
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await client.send_message(chat_id, "🎬 **Latest Streaming Movies:**", reply_markup=reply_markup)

# Pagination navigation
@Client.on_message(filters.text & filters.regex("^(⬅️ Prev|➡️ Next)$"))
async def paginate_movies(client, message):
    user_id = message.from_user.id
    if user_id not in user_pages:
        await message.reply_text("Session expired. Send /latest again.")
        return

    current_page = user_pages[user_id]["page"]
    if message.text == "➡️ Next":
        user_pages[user_id]["page"] = current_page + 1
    elif message.text == "⬅️ Prev" and current_page > 0:
        user_pages[user_id]["page"] = current_page - 1

    await send_movies_page(client, message.chat.id, user_id, user_pages[user_id]["page"])

# Close the reply keyboard
@Client.on_message(filters.text & filters.regex("^❌ Close$"))
async def close_keyboard(client, message):
    await message.reply_text("✅ Closed.", reply_markup=ReplyKeyboardRemove())
