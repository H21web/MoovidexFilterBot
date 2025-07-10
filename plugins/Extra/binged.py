import requests
import re
import html
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from utils import temp
from info import *

# List of Admin IDs
ADMIN_IDS = [1011394081, 7191327005]

# Search API
SEARCH_URL = "https://www.binged.com/wp-json/binged-api/v1/movies"

# Anti-403 Headers
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/85.0.4183.121 Safari/537.36',
    'Referer': 'https://www.binged.com/'
}

# Temporary Data Stores
temp.BINGED_RESULTS = {}   # user_id -> {movie_id: movie_data}
temp.BINGED_STYLE = {}     # admin_id -> style number
temp.EDITING_POST = {}     # admin_id -> movie_id

# Clean HTML entities and unicode
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

# Extract list values from keys
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

# Generate message format by style
def build_binged_message(title, year, movie_type, lang, genres, platform, style, safe_title, bot_username):
    lang_tag = ", ".join(f"#{l.strip().title()}" for l in lang) if isinstance(lang, list) else f"#{lang.strip().title()}" if lang else "N/A"
    genre_str = ", ".join(genres) or "N/A"
    movie_url = f"https://t.me/{bot_username}?start=Search_{safe_title}"

    if style == 1:
        return (
            f"✅ **{title}** · ({year}) · `{movie_type}`\n\n"
            f"🉑 {lang_tag}\n"
            f"🎭 {genre_str} · 📺 {platform}\n"
            f"**@MooviDex**"
        )
    elif style == 2:
        return (
            f"🎬 **[{title}]({movie_url})**\n"
            f"`───────────────`\n"
            f"📆 {year}      · `{movie_type}`\n\n"
            f"🗣️ Language: {lang_tag}\n"
            f"🎭 Genre: {genre_str}\n"
            f"📺 Platform: {platform}\n\n"
            f"📡 **@MooviDex**"
        )
    elif style == 3:
        return (
            f"✅ **[{title}]({movie_url})**\n"
            f"`({year} · {movie_type})`\n\n"
            f"{lang_tag} 🎭 {genre_str} · 📺 {platform}\n\n"
            f"**@MooviDex**"
        )
    elif style == 4:
        return (
            f"🎬 **[{title}]({movie_url})**\n"
            f"`({year} · {movie_type})`\n\n"
            f"🉑 Language: {lang_tag}\n"
            f"🎭 Genres: {genre_str}\n"
            f"📺 Streaming On: {platform}\n\n"
            f"📝 *A compelling drama series.*\n\n"
            f"📢 Powered by **@MooviDex**"
        )
    elif style == 5:
        return (
            f"✨ **[{title}]({movie_url})**\n"
            f"`({year} · {movie_type})`\n\n"
            f"{lang_tag} 🎭 {genre_str}\n"
            f"📺 {platform}\n\n"
            f"🔥 Only on **@MooviDex**"
        )
    return f"✅ **[{title}]({movie_url})** · `({year})  · {movie_type}`\n\n🉑 {lang_tag}\n🎭 {genre_str} · 📺 {platform}\n**@MooviDex**"

# Set style command
@Client.on_message(filters.command("setstyle"))
async def set_style(client, message):
    if message.from_user.id not in ADMIN_IDS:
        return await message.reply_text("🚫 You are not authorized.")
    if len(message.command) < 2:
        return await message.reply_text(
            "Usage: /setstyle <1-5>\n"
            "Available Styles:\n1. Minimalist\n2. Centered Block\n3. Hashtag Style\n4. Detailed\n5. Instagram-style",
            parse_mode="markdown"
        )
    try:
        style = int(message.command[1])
        if style not in range(1, 6): raise ValueError
        temp.BINGED_STYLE[message.from_user.id] = style
        await message.reply_text(f"✅ Style {style} selected.")
    except:
        await message.reply_text("❌ Invalid style number. Use 1–5.")

# /binged command
@Client.on_message(filters.command("binged"))
async def binged_search(client, message):
    if message.from_user.id not in ADMIN_IDS:
        return await message.reply_text("🚫 This command is for admins only.")
    if len(message.command) < 2:
        return await message.reply_text("Usage: /binged <movie name>")

    query = " ".join(message.command[1:]).strip()

    try:
        resp = requests.get(f"{SEARCH_URL}?mode=all&search={query}", headers=HEADERS, timeout=10)
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

# Show movie detail
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
    langs = extract_list(movie, "languages")
    platform_str = extract_list(movie, "platforms", "name")[0] if extract_list(movie, "platforms", "name") else "N/A"
    safe_title = re.sub(r'[^a-zA-Z0-9]', '_', title)
    style = temp.BINGED_STYLE.get(user_id, 1)

    msg = build_binged_message(title, year, movie_type, langs[0] if langs else "Unknown", genres, platform_str, style, safe_title, temp.U_NAME)

    buttons = [[InlineKeyboardButton("🔍 Click to Search", url=f"https://t.me/{temp.U_NAME}?start=Search_{safe_title}")]]
    if user_id in ADMIN_IDS:
        buttons.append([
            InlineKeyboardButton("✏️ Edit & Post", callback_data=f"binged_edit_post_{movie_id}"),
            InlineKeyboardButton("📣 Post Default", callback_data=f"binged_post_{movie_id}")
        ])
    buttons.append([InlineKeyboardButton("❌ Close", callback_data="close_message")])
    await cq.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(buttons), disable_web_page_preview=True)
    await cq.answer()

# Post directly to channel
@Client.on_callback_query(filters.regex(r"^binged_post_(\d+)$"))
async def binged_post(client, cq):
    if cq.from_user.id not in ADMIN_IDS:
        return await cq.answer("You're not authorized.", show_alert=True)
    movie_id = cq.data.split("_")[-1]
    movie = temp.BINGED_RESULTS.get(cq.from_user.id, {}).get(movie_id)
    if not movie:
        return await cq.answer("Movie data not found.", show_alert=True)

    title = clean_text(movie.get("title")) or "Unknown"
    year = movie.get("theatrical-year") or "N/A"
    movie_type = clean_text(movie.get("type")) or "N/A"
    genres = extract_list(movie, "genres")
    langs = extract_list(movie, "languages")
    platform_str = extract_list(movie, "platforms", "name")[0] if extract_list(movie, "platforms", "name") else "N/A"
    safe_title = re.sub(r'[^a-zA-Z0-9]', '_', title)
    style = temp.BINGED_STYLE.get(cq.from_user.id, 1)

    msg = build_binged_message(title, year, movie_type, langs[0] if langs else "Unknown", genres, platform_str, style, safe_title, temp.U_NAME)

    await client.send_message(
        chat_id=POST_CHANNEL_ID,
        text=msg,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔍 Click to Search", url=f"https://t.me/{temp.U_NAME}?start=Search_{safe_title}")]
        ]),
        disable_web_page_preview=True
    )
    await cq.answer("✅ Posted to channel.")

# Prompt for custom button input
@Client.on_callback_query(filters.regex(r"^binged_edit_post_(\d+)$"))
async def edit_post_prompt(client, cq):
    movie_id = cq.data.split("_")[-1]
    user_id = cq.from_user.id
    temp.EDITING_POST[user_id] = movie_id

    await cq.message.reply_text("✏️ Send the **new search keyword** or **full URL** to use in the search button.", quote=True)
    await cq.answer()

# Handle admin reply with custom button
@Client.on_message(filters.text & filters.user(ADMIN_IDS))
async def receive_custom_search(client, message):
    user_id = message.from_user.id
    custom_input = message.text.strip()

    if user_id not in temp.EDITING_POST:
        return

    movie_id = temp.EDITING_POST.pop(user_id)
    movie = temp.BINGED_RESULTS.get(user_id, {}).get(movie_id)
    if not movie:
        return await message.reply("❌ Movie session expired. Please search again.")

    title = clean_text(movie.get("title")) or "Unknown"
    year = movie.get("theatrical-year") or "N/A"
    movie_type = clean_text(movie.get("type")) or "N/A"
    genres = extract_list(movie, "genres")
    langs = extract_list(movie, "languages")
    platform_str = extract_list(movie, "platforms", "name")[0] if extract_list(movie, "platforms", "name") else "N/A"
    safe_title = re.sub(r'[^a-zA-Z0-9]', '_', title)
    style = temp.BINGED_STYLE.get(user_id, 1)

    msg = build_binged_message(title, year, movie_type, langs[0] if langs else "Unknown", genres, platform_str, style, safe_title, temp.U_NAME)

    # Decide URL
    if custom_input.startswith("http://") or custom_input.startswith("https://"):
        button_url = custom_input
    else:
        keyword = re.sub(r'[^a-zA-Z0-9]', '_', custom_input)
        button_url = f"https://t.me/{temp.U_NAME}?start=Search_{keyword}"

    await client.send_message(
        chat_id=POST_CHANNEL_ID,
        text=msg,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔍 Click to Search", url=button_url)]
        ]),
        disable_web_page_preview=True
    )
    await message.reply("✅ Posted to channel with custom button.")

# Close message handler
@Client.on_callback_query(filters.regex(r"^close_message$"))
async def close_message_callback(client, cq):
    try:
        await cq.message.delete()
    except:
        pass
    await cq.answer()
