import requests
import html
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from utils import temp

OTT_URL = "https://www.binged.com/wp-json/binged-api/v1/whats-streaming"
OTT_USER_CACHE = {}  # user_id: {platforms, selected_platform, page}

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

# /ott command handler
@Client.on_message(filters.command("ott"))
async def ott_command_handler(client, message):
    user_id = message.from_user.id
    try:
        response = requests.get(OTT_URL)
        data = response.json()
        platforms = list(data.values())
        OTT_USER_CACHE[user_id] = {"platforms": platforms}

        buttons = [
            [InlineKeyboardButton(clean_text(p['title']), callback_data=f"ott_platform_{i}")]
            for i, p in enumerate(platforms)
        ]
        buttons.append([InlineKeyboardButton("❌ Close", callback_data="ott_close")])
        markup = InlineKeyboardMarkup(buttons)

        await message.reply_text("📺 **Select a Platform to Browse:**", reply_markup=markup)
    except Exception as e:
        await message.reply_text("⚠️ Failed to fetch OTT platforms.")

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
    await show_platform_page(client, callback_query.message, user_id)

# Pagination - show a page of movies
async def show_platform_page(client, message, user_id):
    cache = OTT_USER_CACHE[user_id]
    platform = cache['selected_platform']
    movies = platform.get("movies", [])
    logo = platform.get("platform_logo")
    page = cache.get('page', 0)
    page_size = 8

    start = page * page_size
    end = start + page_size
    current_movies = movies[start:end]

    buttons = []
    for movie in current_movies:
        title = clean_text(movie.get("title", "Untitled"))
        buttons.append([InlineKeyboardButton(title, url=f"https://www.binged.com/movie/{movie['ID']}")])

    nav_buttons = []
    if start > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data="ott_prev"))
    if end < len(movies):
        nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data="ott_next"))
    if nav_buttons:
        buttons.append(nav_buttons)

    buttons.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="ott_back")])
    buttons.append([InlineKeyboardButton("❌ Close", callback_data="ott_close")])

    markup = InlineKeyboardMarkup(buttons)

    caption = f"🎬 **{platform['title']} Movies**\n🖼️ [Platform Logo]({logo})\n\nPage {page + 1} of {(len(movies)-1)//page_size + 1}"

    try:
        await message.edit_text(caption, reply_markup=markup, disable_web_page_preview=False)
    except:
        await message.reply_text(caption, reply_markup=markup, disable_web_page_preview=False)

@Client.on_callback_query(filters.regex("ott_next"))
async def ott_next_page(client, callback_query):
    user_id = callback_query.from_user.id
    OTT_USER_CACHE[user_id]['page'] += 1
    await show_platform_page(client, callback_query.message, user_id)
    await callback_query.answer()

@Client.on_callback_query(filters.regex("ott_prev"))
async def ott_prev_page(client, callback_query):
    user_id = callback_query.from_user.id
    OTT_USER_CACHE[user_id]['page'] -= 1
    await show_platform_page(client, callback_query.message, user_id)
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
    buttons.append([InlineKeyboardButton("❌ Close", callback_data="ott_close")])
    markup = InlineKeyboardMarkup(buttons)
    await callback_query.message.edit_text("📺 **Select a Platform to Browse:**", reply_markup=markup)

@Client.on_callback_query(filters.regex("ott_close"))
async def ott_close_handler(client, callback_query):
    try:
        await callback_query.message.delete()
    except:
        await callback_query.answer("⚠️ Unable to close.")
