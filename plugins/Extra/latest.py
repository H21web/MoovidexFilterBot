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

# Fetch latest movies from Binged API
def fetch_latest_movies():
    url = "https://www.binged.com/wp-json/binged-api/v1/movies"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json",
        "Referer": "https://www.binged.com/",
        "Origin": "https://www.binged.com"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get("data", [])
        else:
            print("Status:", response.status_code)
    except Exception as e:
        print("Error fetching latest movies:", e)
    return []

# /latest command - show ReplyKeyboardMarkup with movie titles in 2 columns
@Client.on_message(filters.command("latest"))
async def latest_movies_command(client, message):
    movies_data = fetch_latest_movies()
    if not movies_data:
        await message.reply_text("⚠️ No latest movies found or failed to fetch.")
        return

    keyboard = []
    row = []
    for index, movie in enumerate(reversed(movies_data)):  # Newest to oldest
        title = clean_text(movie.get("title", "Untitled"))
        row.append(KeyboardButton(title))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([KeyboardButton("❌ Close")])
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await message.reply_text("🎬 **Latest Streaming Movies:**", reply_markup=reply_markup)

# ❌ Close button handler
@Client.on_message(filters.text & filters.regex("^❌ Close$"))
async def close_keyboard(client, message):
    await message.reply_text("✅ Closed.", reply_markup=ReplyKeyboardRemove())
