import requests
import re
import html
from bs4 import BeautifulSoup
from pyrogram import Client, filters
from pyrogram.types import ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton

# Clean HTML entities and special characters
def clean_text(text):
    if not text:
        return text
    text = html.unescape(text)
    text = text.replace('\u2019', "'").replace('\u2018', "'")
    text = text.replace('\u201c', '"').replace('\u201d', '"')
    text = text.replace('\u2013', '-').replace('\u2014', '-')
    text = text.replace('\u2026', '...')
    return text.strip()

# Scrape titles from https://www.binged.com/streaming-today/
def fetch_movie_titles():
    try:
        url = "https://www.binged.com/streaming-today/"
        headers = {
            "User-Agent": "Mozilla/5.0"
        }
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, "html.parser")
        titles = []
        for block in soup.select(".release-card-title"):
            title = clean_text(block.text)
            if title:
                titles.append(title)
        return titles
    except Exception as e:
        print("Error fetching movies:", e)
        return []

# /latest command - show movie titles in 2-column ReplyKeyboardMarkup
@Client.on_message(filters.command("latest"))
async def latest_movies_command(client, message):
    titles = fetch_movie_titles()
    if not titles:
        await message.reply_text("⚠️ No movies found or failed to fetch.")
        return

    keyboard = []
    row = []
    for i, title in enumerate(titles):
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
