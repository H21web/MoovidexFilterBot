import requests
import html
from pyrogram import Client, filters
from pyrogram.types import ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton

# Clean HTML entities and unicode characters
def clean_text(text):
    if not text:
        return text
    text = html.unescape(text)
    text = text.replace('\u2019', "'").replace('\u2018', "'")
    text = text.replace('\u201c', '"').replace('\u201d', '"')
    text = text.replace('\u2013', '-').replace('\u2014', '-')
    text = text.replace('\u2026', '...')
    return text

# Fetch latest movies from mirror source
def fetch_latest_movies():
    url = "https://bingeddata.pages.dev/api/streaming-today.json"
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Referer': 'https://www.binged.com/'
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get('data', []) or data  # Support multiple formats
    except Exception as e:
        print("Error fetching latest movies:", e)
    return []

# /latest command - show reply keyboard with latest movie titles
@Client.on_message(filters.command("latest"))
async def latest_movies_command(client, message):
    movies_data = fetch_latest_movies()
    if not movies_data:
        await message.reply_text("⚠️ No latest movies found or failed to fetch.")
        return

    keyboard = []
    for movie in reversed(movies_data):  # Newest to oldest
        title = clean_text(movie.get("title", "Untitled"))
        keyboard.append([KeyboardButton(title)])

    keyboard.append([KeyboardButton("❌ Close")])
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await message.reply_text("🎬 **Latest Streaming Movies:**", reply_markup=reply_markup)

# Close keyboard when "❌ Close" is clicked
@Client.on_message(filters.text & filters.regex("^❌ Close$"))
async def close_keyboard(client, message):
    await message.reply_text("✅ Closed.", reply_markup=ReplyKeyboardRemove())
