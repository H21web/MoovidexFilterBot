import requests
import re
import html
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from utils import temp
from info import *

# List of Admin IDs
ADMIN_IDS = [1011394081, 7191327005]  # Replace with your actual admin user IDs

# Base URLs
SEARCH_URL = "https://www.binged.com/wp-json/binged-api/v1/movies"
DETAIL_URL = "https://www.binged.com/wp-json/binged-api/v1/movie"

# Helper: clean HTML entities & weird unicode
def clean_text(text):
    if not text:
        return text
    text = html.unescape(text)
    for orig, sub in [
        ("\u2019", "'"),  # right single quote
        ("\u2018", "'"),  # left single quote
        ("\u201c", '"'),  # left double quote
        ("\u201d", '"'),  # right double quote
        ("\u2013", "-"),  # en dash
        ("\u2014", "-"),  # em dash
        ("\u2026", "...") # ellipsis
    ]:
        text = text.replace(orig, sub)
    return text.strip()

# /binged – search handler
@Client.on_message(filters.command("binged"))
async def binged_search(client, message):
    if len(message.command) < 2:
        return await message.reply_text(
            "❗ Usage: `/binged <movie name>`",
            parse_mode="markdown"
        )
    query = " ".join(message.command[1:])

    # 🔧 Use mode=all to ensure full search coverage
    try:
        resp = requests.get(f"{SEARCH_URL}?mode=all&search={query}", timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        return await message.reply_text(
            f"⚠️ Failed to reach search API. Please try again later.\n`{e}`",
            parse_mode="markdown"
        )

    data = resp.json().get("data", [])
    if not data:
        return await message.reply_text("🔍 No results found.")

    # Build buttons: Title (Year) → callback carrying movie ID
    buttons = []
    for movie in data:
        title = clean_text(movie.get("title", "Untitled"))
        year  = movie.get("theatrical-year", "N/A")
        movie_id = movie.get("id")
        btn_text = f"{title} ({year})"
        buttons.append([
            InlineKeyboardButton(btn_text, callback_data=f"binged_detail_{movie_id}")
        ])

    buttons.append([InlineKeyboardButton("❌ Close", callback_data="close_message")])
    await message.reply_text(
        f"🔍 Search results for **{clean_text(query)}**:",
        parse_mode="markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# Detail callback – fetch full info & show “post to channel” for admins
@Client.on_callback_query(filters.regex(r"^binged_detail_(\d+)$"))
async def binged_detail(client, cq):
    movie_id = cq.data.split("_")[-1]
    try:
        resp = requests.get(f"{DETAIL_URL}/{movie_id}", timeout=10)
        resp.raise_for_status()
    except requests.RequestException:
        return await cq.answer("⚠️ Could not fetch movie details.", show_alert=True)

    m = resp.json()
    title = clean_text(m.get("title", "N/A"))
    year = m.get("theatrical-year", "N/A")
    typ  = clean_text(m.get("type", "N/A"))
    genres = ", ".join(clean_text(g) for g in m.get("genres", [])) or "N/A"
    langs  = ", ".join(clean_text(l) for l in m.get("languages", [])) or "N/A"
    plat   = ", ".join(p.get("name","") for p in m.get("platforms", [])) or "N/A"
    streaming = m.get("streaming-date", "Unknown")

    details = (
        f"✅ **{title}** · ({year})\n"
        f"🎥 {typ} · 🎭 {genres}\n"
        f"🉑 {langs} · 📺 {plat}\n"
        f"📅 Streaming from: {streaming}"
    )

    # Buttons: Search button always, plus Post-to-channel if admin
    search_btn = InlineKeyboardButton(
        "🔍 Search in Bot",
        url=f"https://t.me/{temp.U_NAME}?start=Search_{re.sub(r'[^a-zA-Z0-9]', '_', title)}_{year}"
    )
    markup = [[search_btn]]
    if cq.from_user.id in ADMIN_IDS:
        markup.append([
            InlineKeyboardButton("📣 Post to Channel", callback_data=f"binged_post_{movie_id}")
        ])
    markup.append([InlineKeyboardButton("❌ Close", callback_data="close_message")])

    await cq.message.reply_text(
        details,
        parse_mode="markdown",
        reply_markup=InlineKeyboardMarkup(markup)
    )
    await cq.answer()

# Post-to-channel callback – for admins only
@Client.on_callback_query(filters.regex(r"^binged_post_(\d+)$"))
async def binged_post(client, cq):
    if cq.from_user.id not in ADMIN_IDS:
        return await cq.answer("🚫 You’re not authorized.", show_alert=True)

    movie_id = cq.data.split("_")[-1]
    try:
        resp = requests.get(f"{DETAIL_URL}/{movie_id}", timeout=10)
        resp.raise_for_status()
    except requests.RequestException:
        return await cq.answer("⚠️ Could not fetch details.", show_alert=True)

    m = resp.json()
    title = clean_text(m.get("title", "N/A"))
    year = m.get("theatrical-year", "N/A")
    typ  = clean_text(m.get("type", "N/A"))
    genres = ", ".join(clean_text(g) for g in m.get("genres", [])) or "N/A"
    langs  = ", ".join(clean_text(l) for l in m.get("languages", [])) or "N/A"
    plat   = ", ".join(p.get("name","") for p in m.get("platforms", [])) or "N/A"
    streaming = m.get("streaming-date", "Unknown")

    post_text = (
        f"✅ **{title}** · ({year})\n"
        f"🎥 {typ}\n"
        f"🎭 {genres} · 🉑 {langs}\n"
        f"📺 {plat}\n"
        f"📅 Streaming from: {streaming}\n\n"
        f"**@MooviDex**"
    )
    search_btn = InlineKeyboardButton(
        "🔍 Search in Bot",
        url=f"https://t.me/{temp.U_NAME}?start=Search_{re.sub(r'[^a-zA-Z0-9]', '_', title)}_{year}"
    )
    try:
        channel_id = "-1001680629032"  # Replace with your channel ID
        await client.send_message(
            chat_id=channel_id,
            text=post_text,
            parse_mode="markdown",
            reply_markup=InlineKeyboardMarkup([[search_btn]])
        )
        await cq.answer("✅ Posted to channel.")
    except Exception as e:
        await cq.answer(f"⚠️ Post failed: {e}", show_alert=True)

# Close-button handler
@Client.on_callback_query(filters.regex(r"^close_message$"))
async def close_message_callback(client, cq):
    try:
        await cq.message.delete()
    except:
        pass
    await cq.answer()
