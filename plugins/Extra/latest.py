import requests
import html
from pyrogram import Client, filters
from pyrogram.types import ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton

# Function to decode and clean text
def clean_text(text):
    if not text:
        return text
    text = html.unescape(text)
    replacements = {
        '\u2019': "'", '\u2018': "'",
        '\u201c': '"', '\u201d': '"',
        '\u2013': '-', '\u2014': '-',
        '\u2026': '...'
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.strip()

# Fetch all latest movies (handles pagination)
def fetch_latest_movies():
    base_url = "https://www.binged.com/wp-json/binged-api/v1/movies?mode=streaming-week"
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Referer': 'https://www.binged.com/'
    }

    all_movies = []
    page = 1

    while True:
        try:
            url = f"{base_url}&page={page}" if page > 1 else base_url
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                break

            data = response.json()
            page_movies = data.get("data", [])
            if not page_movies:
                break

            all_movies.extend(page_movies)
            total_pages = data.get("pagination", {}).get("total_pages", 1)
            if page >= total_pages:
                break
            page += 1

        except Exception as e:
            print("Error fetching movies:", e)
            break

    return all_movies

# Global dictionary to track users' movie pages
user_pages = {}

# Handle /latest command
@Client.on_message(filters.command("latest"))
async def latest_movies_command(client, message):
    user_id = message.from_user.id
    movies = fetch_latest_movies()

    if not movies:
        await message.reply_text("⚠️ Failed to fetch latest movies.")
        return

    # Clean and prepare titles with internal serial (not shown)
    titles = [(i + 1, clean_text(movie.get("title", "Untitled"))) for i, movie in enumerate(movies)]
    user_pages[user_id] = {"titles": titles, "page": 0}

    await send_movies_page(client, message.chat.id, user_id, 0)

# Send one page of movies as keyboard
async def send_movies_page(client, chat_id, user_id, page):
    titles = user_pages[user_id]["titles"]
    page_size = 20  # 2 columns, 10 rows
    start = page * page_size
    end = start + page_size
    current_titles = titles[start:end]

    keyboard = []
    row = []
    for _, title in current_titles:
        row.append(KeyboardButton(title))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    nav_row = []
    if page > 0:
        nav_row.append(KeyboardButton("⬅️ Prev"))
    if end < len(titles):
        nav_row.append(KeyboardButton("➡️ Next"))
    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([KeyboardButton("❌ Close")])
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    # Send and delete placeholder message
    placeholder = await client.send_message(chat_id, "🎬 Latest Streaming Movies:", reply_markup=reply_markup)
    await placeholder.delete()

# Handle next/prev pagination buttons
@Client.on_message(filters.text & filters.regex("^(⬅️ Prev|➡️ Next)$"))
async def paginate_movies(client, message):
    user_id = message.from_user.id
    if user_id not in user_pages:
        await message.delete()
        return

    current_page = user_pages[user_id]["page"]
    if message.text == "➡️ Next":
        user_pages[user_id]["page"] = current_page + 1
    elif message.text == "⬅️ Prev" and current_page > 0:
        user_pages[user_id]["page"] = current_page - 1

    await message.delete()
    await send_movies_page(client, message.chat.id, user_id, user_pages[user_id]["page"])

# Handle Close button
@Client.on_message(filters.text & filters.regex("^❌ Close$"))
async def close_keyboard(client, message):
    await message.delete()
    await client.send_message(message.chat.id, ".", reply_markup=ReplyKeyboardRemove())
