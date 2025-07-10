import requests
import re
import html
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from utils import temp
from info import *

# List of Admin IDs
ADMIN_IDS = [1011394081, 7191327005]

# Search URL
SEARCH_URL = "https://www.binged.com/wp-json/binged-api/v1/movies"

# Headers
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/85.0.4183.121 Safari/537.36',
    'Referer': 'https://www.binged.com/'
}

# Temporary cache: user_id -> { movie_id: movie_data }
temp.BINGED_RESULTS = {}

def clean_text(text):
    if not isinstance(text, str):
        return ""
    text = html.unescape(text)
    for orig, sub in [
        ("\u2019", "'"), ("\u2018", "'"),
        ("\u201c", '"'), ("\u201d", '"'),
        ("\u2013", "-"), ("\u2014", "-"),
        ("\u2026", "...")
    ]:
        text = text.replace(orig, sub)
    return text.strip()

def extract_list(data, key, nested_key=None):
    items = data.get(key)
    if not isinstance(items, list):
        return "N/A"
    result = []
    for i in items:
        val = i.get(nested_key) if nested_key and isinstance(i, dict) else i
        val = clean_text(val)
        if val:
            result.append(val)
    return ", ".join(result) or "N/A"

# /binged search
@Client.on_message(filters.command("binged"))
async def binged_search(client, message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: /binged <movie name>")
    query = " ".join(message.command[1:]).strip()

    try:
        resp = requests.get(
            f"{SEARCH_URL}?mode=all&search={query}",
            headers=HEADERS,
            timeout=10
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        return await message.reply_text(f"API error: {e}")

    results = resp.json().get("data", [])
    if not results:
        return await message.reply_text("No results found.")

    temp.BINGED_RESULTS[message.from_user.id] = {}

    buttons = []
    for movie in results:
        movie_id = str(movie.get("id"))
        title = clean_text(movie.get("title"))
        year = movie.get("theatrical-year") or "N/A"
        btn_text = f"{title} ({year})"
        temp.BINGED_RESULTS[message.from_user.id][movie_id] = movie
        buttons.append([InlineKeyboardButton(btn_text, callback_data=f"binged_detail_{movie_id}")])

    buttons.append([InlineKeyboardButton("Close ❌", callback_data="close_message")])

    await message.reply_text(
        f"Search results for: <b>{query}</b>",
        reply_markup=InlineKeyboardMarkup(buttons),
        disable_web_page_preview=True
    )

# Movie detail (from cached search result)
@Client.on_callback_query(filters.regex(r"^binged_detail_(\d+)$"))
async def binged_detail(client, cq):
    movie_id = cq.data.split("_")[-1]
    user_id = cq.from_user.id

    movie_data = temp.BINGED_RESULTS.get(user_id, {}).get(movie_id)
    if not movie_data:
        return await cq.answer("Session expired. Search again.", show_alert=True)

    title = clean_text(movie_data.get("title"))
    year = movie_data.get("theatrical-year") or "N/A"
    typ = clean_text(movie_data.get("type")) or "N/A"
    genres = extract_list(movie_data, "genres")
    langs = extract_list(movie_data, "languages")
    platforms = extract_list(movie_data, "platforms", "name")
    streaming = movie_data.get("streaming-date") or "Unknown"

    details = (
        f"{title} ({year})\n"
        f"Type: {typ}\n"
        f"Genres: {genres}\n"
        f"Languages: {langs}\n"
        f"Platforms: {platforms}\n"
        f"Streaming from: {streaming}"
    )

    search_btn = InlineKeyboardButton(
        "Search in Bot 🔍",
        url=f"https://t.me/{temp.U_NAME}?start=Search_{re.sub(r'[^a-zA-Z0-9]', '_', title)}_{year}"
    )

    markup = [[search_btn]]
    if user_id in ADMIN_IDS:
        markup.append([InlineKeyboardButton("Post to Channel 📣", callback_data=f"binged_post_{movie_id}")])
    markup.append([InlineKeyboardButton("Close ❌", callback_data="close_message")])

    await cq.message.reply_text(details, reply_markup=InlineKeyboardMarkup(markup))
    await cq.answer()

# Post to channel
@Client.on_callback_query(filters.regex(r"^binged_post_(\d+)$"))
async def binged_post(client, cq):
    if cq.from_user.id not in ADMIN_IDS:
        return await cq.answer("You’re not authorized.", show_alert=True)

    movie_id = cq.data.split("_")[-1]
    movie_data = temp.BINGED_RESULTS.get(cq.from_user.id, {}).get(movie_id)
    if not movie_data:
        return await cq.answer("Movie data not found in session.", show_alert=True)

    title = clean_text(movie_data.get("title"))
    year = movie_data.get("theatrical-year") or "N/A"
    typ = clean_text(movie_data.get("type")) or "N/A"
    genres = extract_list(movie_data, "genres")
    langs = extract_list(movie_data, "languages")
    platforms = extract_list(movie_data, "platforms", "name")
    streaming = movie_data.get("streaming-date") or "Unknown"

    post_text = (
        f"{title} ({year})\n"
        f"Type: {typ}\n"
        f"Genres: {genres}\n"
        f"Languages: {langs}\n"
        f"Platforms: {platforms}\n"
        f"Streaming from: {streaming}\n\n"
        f"@MooviDex"
    )

    search_btn = InlineKeyboardButton(
        "Search in Bot 🔍",
        url=f"https://t.me/{temp.U_NAME}?start=Search_{re.sub(r'[^a-zA-Z0-9]', '_', title)}_{year}"
    )

    try:
        await client.send_message(
            chat_id="-1001680629032",  # Replace with your channel ID
            text=post_text,
            reply_markup=InlineKeyboardMarkup([[search_btn]])
        )
        await cq.answer("Posted to channel.")
    except Exception as e:
        await cq.answer(f"Failed to post: {e}", show_alert=True)

# Close button
@Client.on_callback_query(filters.regex(r"^close_message$"))
async def close_message_callback(client, cq):
    try:
        await cq.message.delete()
    except:
        pass
    await cq.answer()
