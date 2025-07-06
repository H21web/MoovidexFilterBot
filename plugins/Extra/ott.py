import requests
import html
import time
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.types import CallbackQuery
from utils import temp

OTT_URL = "https://www.binged.com/wp-json/binged-api/v1/whats-streaming"
OTT_USER_CACHE = {}  # user_id: {platforms, selected_platform, page}

PLATFORM_IMAGES = {
    "amazon": "https://envs.sh/FI0.jpg",
    "netflix": "https://envs.sh/FIS.jpg",
    "zee5": "https://envs.sh/FIW.jpg",
    "aha video": "https://envs.sh/FIB.jpg",
    "hoichoi": "https://envs.sh/FII.jpg",
    "jio cinema": "https://envs.sh/FIn.jpg",
    "sun nxt": "https://envs.sh/FIT.jpg",
}

# Utility to clean up titles
def clean_text(text):
    if not text:
        return text
    text = html.unescape(text)
    text = text.replace('\u2019', "'").replace('\u2018', "'")
    text = text.replace('\u201c', '"').replace('\u201d', '"')
    text = text.replace('\u2013', '-').replace('\u2014', '-')
    text = text.replace('\u2026', '...')
    return text

# Helper to fetch OTT data with retry
def fetch_ott_data():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.binged.com/",
        "Origin": "https://www.binged.com"
    }
    try:
        response = requests.get(OTT_URL, headers=headers, timeout=10)
        if response.status_code == 520:
            time.sleep(2)
            response = requests.get(OTT_URL, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e)}

# /ott command handler
@Client.on_message(filters.command("ott"))
async def ott_command_handler(client, event):
    # Handle both /ott command and button clicks
    if isinstance(event, CallbackQuery):
        user_id = event.from_user.id
        message = event.message
    else:  # It's a Message (from command)
        user_id = event.from_user.id
        message = event

    data = fetch_ott_data()

    if "error" in data:
        await message.reply_text(f"⚠️ Failed to fetch OTT platforms.\nError: {data['error']}")
        return

    if not isinstance(data, dict):
        await message.reply_text("⚠️ Invalid response received from OTT source.")
        return

    platforms = list(data.values())
    if not platforms:
        await message.reply_text("🚫 No platforms found.")
        return

    OTT_USER_CACHE[user_id] = {"platforms": platforms}

    buttons = [
        [InlineKeyboardButton(clean_text(p['title']), callback_data=f"ott_platform_{i}")]
        for i, p in enumerate(platforms)
    ]
    buttons.append([InlineKeyboardButton("🔙 Close", callback_data="ott_close")])
    markup = InlineKeyboardMarkup(buttons)

    await message.reply_text("📺 **Select a Platform to Browse:**", reply_markup=markup)

# Show movies for selected platform
@Client.on_callback_query(filters.regex("ott_platform_"))
async def platform_selected(client, callback_query):
    user_id = callback_query.from_user.id
    index = int(callback_query.data.split("ott_platform_")[1])
    cache = OTT_USER_CACHE.get(user_id)

    if not cache:
        return await callback_query.answer("⚠️ Session expired. Send /ott again.", show_alert=True)

    platform = cache['platforms'][index]
    cache['selected_platform'] = platform
    cache['page'] = 0

    await callback_query.message.delete()
    await show_platform_page(client, callback_query.message, user_id, send_as_new=True)

# Pagination - show a page of movies
async def show_platform_page(client, message, user_id, send_as_new=False):
    cache = OTT_USER_CACHE[user_id]
    platform = cache['selected_platform']
    movies = platform.get("movies", [])
    title = platform.get("title", "Unknown Platform")
    platform_key = title.lower().strip()
    logo = PLATFORM_IMAGES.get(platform_key, "")
    page = cache.get('page', 0)
    page_size = 8

    start = page * page_size
    end = start + page_size
    current_movies = movies[start:end]

    buttons = []
    for movie in current_movies:
        title = clean_text(movie.get("title", "Untitled"))
        buttons.append([InlineKeyboardButton(title, url=f"https://t.me/{temp.U_NAME}?start=Search_{title}")])

    nav_buttons = []
    if start > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data="ott_prev"))
    if end < len(movies):
        nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data="ott_next"))
    if nav_buttons:
        buttons.append(nav_buttons)

    buttons.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="ott_back")])

    markup = InlineKeyboardMarkup(buttons)
    caption = f"🎬 **{platform['title']} Movies**\n\nPage {page + 1} of {(len(movies)-1)//page_size + 1}"

    if logo:
        await client.send_photo(
            message.chat.id,
            photo=logo,
            caption=caption,
            reply_markup=markup
        )
    else:
        await client.send_message(message.chat.id, text=caption, reply_markup=markup)

@Client.on_callback_query(filters.regex("ott_next"))
async def ott_next_page(client, callback_query):
    user_id = callback_query.from_user.id
    OTT_USER_CACHE[user_id]['page'] += 1
    await callback_query.message.delete()
    await show_platform_page(client, callback_query.message, user_id, send_as_new=True)
    await callback_query.answer()

@Client.on_callback_query(filters.regex("ott_prev"))
async def ott_prev_page(client, callback_query):
    user_id = callback_query.from_user.id
    OTT_USER_CACHE[user_id]['page'] -= 1
    await callback_query.message.delete()
    await show_platform_page(client, callback_query.message, user_id, send_as_new=True)
    await callback_query.answer()

@Client.on_callback_query(filters.regex("ott_back"))
async def ott_back_to_main(client, callback_query):
    user_id = callback_query.from_user.id
    cache = OTT_USER_CACHE.get(user_id)
    if not cache:
        return await callback_query.answer("⚠️ Session expired.", show_alert=True)

    buttons = [
        [InlineKeyboardButton(clean_text(p['title']), callback_data=f"ott_platform_{i}")]
        for i, p in enumerate(cache['platforms'])
    ]
    buttons.append([InlineKeyboardButton("🔙 Close", callback_data="ott_close")])
    markup = InlineKeyboardMarkup(buttons)
    await callback_query.message.edit_text("📺 **Select a Platform to Browse:**", reply_markup=markup)

@Client.on_callback_query(filters.regex("ott_close"))
async def ott_close_handler(client, callback_query):
    try:
        await callback_query.message.delete()
    except:
        await callback_query.answer("⚠️ Unable to close.")
