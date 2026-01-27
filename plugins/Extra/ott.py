import aiohttp
import asyncio
import html
import time
from datetime import datetime, timedelta
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, InputMediaPhoto
from utils import temp
from urllib.parse import quote_plus

OTT_URL = "https://www.binged.com/wp-json/binged-api/v1/whats-streaming"

# Cache per message ID to support session tracking
OTT_USER_CACHE = {}  # message_id: {user_id, platforms, selected_platform, page, timestamp}

PLATFORM_IMAGES = {
    "amazon": "https://envs.sh/FI0.jpg",
    "netflix": "https://envs.sh/FIS.jpg",
    "zee5": "https://envs.sh/FIW.jpg",
    "aha video": "https://envs.sh/FIB.jpg",
    "hoichoi": "https://envs.sh/FII.jpg",
    "jio cinema": "https://envs.sh/FIn.jpg",
    "sun nxt": "https://envs.sh/FIT.jpg",
}

def clean_text(text):
    if not text:
        return text
    text = html.unescape(text)
    text = text.replace('\u2019', "'").replace('\u2018', "'")
    text = text.replace('\u201c', '"').replace('\u201d', '"')
    text = text.replace('\u2013', '-').replace('\u2014', '-')
    text = text.replace('\u2026', '...')
    return text

async def fetch_ott_data():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.binged.com/",
        "Origin": "https://www.binged.com"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(OTT_URL, headers=headers, timeout=10) as response:
                if response.status == 520:
                    await asyncio.sleep(2)
                    async with session.get(OTT_URL, headers=headers, timeout=10) as response2:
                         if response2.status != 200:
                             return {"error": f"Status {response2.status}"}
                         return await response2.json()
                if response.status != 200:
                    return {"error": f"Status {response.status}"}
                return await response.json()
    except Exception as e:
        return {"error": str(e)}

# 🧼 Session cleaner
def clean_expired_cache(timeout_minutes=5):
    now = datetime.now()
    expired = []

    for msg_id, data in OTT_USER_CACHE.items():
        if "timestamp" in data and now - data["timestamp"] > timedelta(minutes=timeout_minutes):
            expired.append(msg_id)

    for msg_id in expired:
        OTT_USER_CACHE.pop(msg_id, None)

# /ott command handler
@Client.on_message(filters.command("ott"))
async def ott_command_handler(client, event):
    user_id = event.from_user.id
        # Handle both /ott command and button clicks
    if isinstance(event, CallbackQuery):
        user_id = event.from_user.id
        message = event.message
    else:  # It's a Message (from command)
        user_id = event.from_user.id
        message = event

    data = await fetch_ott_data()
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

    buttons = [
        [InlineKeyboardButton(clean_text(p['title']), callback_data=f"ott_platform_{i}")]
        for i, p in enumerate(platforms)
    ]
    buttons.append([InlineKeyboardButton("🔙 Close", callback_data="ott_close")])
    markup = InlineKeyboardMarkup(buttons)

    sent = await message.reply_text("📺 **Select a Platform to Browse:**", reply_markup=markup)
    
    OTT_USER_CACHE[sent.id] = {
        "user_id": user_id,
        "platforms": platforms,
        "timestamp": datetime.now()
    }

@Client.on_callback_query(filters.regex("ott_platform_"))
async def platform_selected(client, callback_query):
    clean_expired_cache()

    user_id = callback_query.from_user.id
    message = callback_query.message
    message_id = message.id

    cache = OTT_USER_CACHE.get(message_id)
    if not cache or cache["user_id"] != user_id:
        return await callback_query.answer("⚠️ Session expired. Send /ott again.", show_alert=True)

    index = int(callback_query.data.split("ott_platform_")[1])
    platform = cache['platforms'][index]

    cache['selected_platform'] = platform
    cache['page'] = 0
    cache['timestamp'] = datetime.now()

    await callback_query.message.delete()
    await show_platform_page(client, message, message_id, user_id)

async def show_platform_page(client, message, message_id, user_id):
    cache = OTT_USER_CACHE.get(message_id)
    if not cache:
        return

    platform = cache.get('selected_platform')
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
        m_title = clean_text(movie.get("title", "Untitled"))
        encoded_title = quote_plus(m_title).replace("+", "_")
        buttons.append([InlineKeyboardButton(m_title, url=f"https://t.me/moovidexrobot?start=Search_{encoded_title}")])

    nav_buttons = []
    if start > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data="ott_prev"))
    if end < len(movies):
        nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data="ott_next"))
    if nav_buttons:
        buttons.append(nav_buttons)

    buttons.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="ott_back")])
    markup = InlineKeyboardMarkup(buttons)
    caption = f"🎬 **{platform['title']} Movies**\n\nPage {page + 1} of {(len(movies) - 1) // page_size + 1}"

    if logo:
        try:
            await message.edit_media(
                media=InputMediaPhoto(media=logo, caption=caption),
                reply_markup=markup
            )
        except Exception:
            new_msg = await client.send_photo(message.chat.id, photo=logo, caption=caption, reply_markup=markup)
            OTT_USER_CACHE[new_msg.id] = OTT_USER_CACHE.pop(message.id)
    else:
        try:
            await message.edit_text(caption, reply_markup=markup)
        except Exception:
            new_msg = await client.send_message(message.chat.id, text=caption, reply_markup=markup)
            OTT_USER_CACHE[new_msg.id] = OTT_USER_CACHE.pop(message.id)


@Client.on_callback_query(filters.regex("ott_next"))
async def ott_next_page(client, callback_query):
    clean_expired_cache()

    user_id = callback_query.from_user.id
    message = callback_query.message
    message_id = message.id

    cache = OTT_USER_CACHE.get(message_id)
    if not cache:
        return await callback_query.answer("⚠️ Session expired.", show_alert=True)

    cache['page'] += 1
    cache['timestamp'] = datetime.now()

    await callback_query.message.delete()
    await show_platform_page(client, message, message_id, user_id)
    await callback_query.answer()

@Client.on_callback_query(filters.regex("ott_prev"))
async def ott_prev_page(client, callback_query):
    clean_expired_cache()

    user_id = callback_query.from_user.id
    message = callback_query.message
    message_id = message.id

    cache = OTT_USER_CACHE.get(message_id)
    if not cache or cache['page'] <= 0:
        return await callback_query.answer("⚠️ Session expired or invalid page.", show_alert=True)

    cache['page'] -= 1
    cache['timestamp'] = datetime.now()

    await callback_query.message.delete()
    await show_platform_page(client, message, message_id, user_id)
    await callback_query.answer()

@Client.on_callback_query(filters.regex("ott_back"))
async def ott_back_to_main(client, callback_query):
    clean_expired_cache()

    user_id = callback_query.from_user.id
    message = callback_query.message
    message_id = message.id

    cache = OTT_USER_CACHE.get(message_id)
    if not cache or cache["user_id"] != user_id:
        return await callback_query.answer("⚠️ Session expired.", show_alert=True)

    buttons = [
        [InlineKeyboardButton(clean_text(p['title']), callback_data=f"ott_platform_{i}")]
        for i, p in enumerate(cache['platforms'])
    ]
    buttons.append([InlineKeyboardButton("🔙 Close", callback_data="ott_close")])
    markup = InlineKeyboardMarkup(buttons)

    cache['timestamp'] = datetime.now()
    await callback_query.message.edit_text("📺 **Select a Platform to Browse:**", reply_markup=markup)

@Client.on_callback_query(filters.regex("ott_close"))
async def ott_close_handler(client, callback_query):
    try:
        await callback_query.message.delete()
    except:
        await callback_query.answer("⚠️ Unable to close.")
