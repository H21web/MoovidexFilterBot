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

# Headers to avoid 403
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/85.0.4183.121 Safari/537.36',
    'Referer': 'https://www.binged.com/'
}

# Temporary storage for search results: user_id -> { movie_id: data }
temp.BINGED_RESULTS = {}

# Clean HTML and unicode
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

# Helper to extract list safely
def extract_list(data, key, nested_key=None):
    items = data.get(key)
    if not isinstance(items, list):
        return []
    result = []
    for i in items:
        val = i.get(nested_key) if nested_key and isinstance(i, dict) else i
        val = clean_text(val)
        if val:
            result.append(val)
    return result

# /binged search handler
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

# Show movie details from cached result
@Client.on_callback_query(filters.regex(r"^binged_detail_(\d+)$"))
async def binged_detail(client, cq):
    movie_id = cq.data.split("_")[-1]
    user_id = cq.from_user.id

    movie = temp.BINGED_RESULTS.get(user_id, {}).get(movie_id)
    if not movie:
        return await cq.answer("Session expired. Please search again.", show_alert=True)

    title = clean_text(movie.get("title")) or "Unknown"
    year = movie.get("theatrical-year") or "N/A"
    movie_type = clean_text(movie.get("type")) or "N/A"
    genres = extract_list(movie, "genres")
    genre_str = ", ".join(genres) or "N/A"
    langs = extract_list(movie, "languages")
    lang_str = ", ".join(langs) or "N/A"
    platforms = extract_list(movie, "platforms", "name")
    platform_str = platforms[0] if platforms else "N/A"

    msg = (
        f"✅ **{title}** · ({year})\n"
        f"🎥 {movie_type}\n"
        f"🎭 {genre_str} · 🉑 {lang_str}\n"
        f"📺 {platform_str}\n"
        f"**@MooviDex**"
    )

    search_btn = InlineKeyboardButton(
        "Click to Search 🔎",
        url=f"https://t.me/{temp.U_NAME}?start=Search_{re.sub(r'[^a-zA-Z0-9]', '_', title)}_{year}"
    )

    buttons = [[search_btn]]
    if user_id in ADMIN_IDS:
        buttons.append([InlineKeyboardButton("Post to Channel 📣", callback_data=f"binged_post_{movie_id}")])
    buttons.append([InlineKeyboardButton("Close ❌", callback_data="close_message")])

    await cq.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(buttons))
    await cq.answer()

# Post movie to channel (for admins)
@Client.on_callback_query(filters.regex(r"^binged_post_(\d+)$"))
async def binged_post(client, cq):
    if cq.from_user.id not in ADMIN_IDS:
        return await cq.answer("You're not authorized.", show_alert=True)

    movie_id = cq.data.split("_")[-1]
    movie = temp.BINGED_RESULTS.get(cq.from_user.id, {}).get(movie_id)
    if not movie:
        return await cq.answer("Movie data not found in session.", show_alert=True)

    title = clean_text(movie.get("title")) or "Unknown"
    year = movie.get("theatrical-year") or "N/A"
    movie_type = clean_text(movie.get("type")) or "N/A"
    genres = extract_list(movie, "genres")
    genre_str = ", ".join(genres) or "N/A"
    langs = extract_list(movie, "languages")
    lang_str = ", ".join(langs) or "N/A"
    platforms = extract_list(movie, "platforms", "name")
    platform_str = platforms[0] if platforms else "N/A"

    post_text = (
        f"✅ **{title}** · ({year})\n"
        f"🎥 {movie_type}\n"
        f"🎭 {genre_str} · 🉑 {lang_str}\n"
        f"📺 {platform_str}\n"
        f"**@MooviDex**"
    )

    search_btn = InlineKeyboardButton(
        "Click to Search 🔎",
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
        await cq.answer(f"Post failed: {e}", show_alert=True)

# Close button
@Client.on_callback_query(filters.regex(r"^close_message$"))
async def close_message_callback(client, cq):
    try:
        await cq.message.delete()
    except:
        pass
    await cq.answer()
