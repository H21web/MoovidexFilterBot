import requests
from pyrogram import Client, filters
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
)

OTT_URL = "https://www.binged.com/wp-json/binged-api/v1/whats-streaming"
ott_data_cache = {}     # platform -> movie list
user_movie_state = {}   # user_id -> {"platform": ..., "page": ...}


def fetch_ott_data():
    try:
        resp = requests.get(OTT_URL, timeout=10)
        return resp.json()
    except Exception:
        return {}

@Client.on_message(filters.command("ott"))
async def ott_command(client: Client, message: Message):
    data = fetch_ott_data()
    if not data:
        return await message.reply_text("⚠️ Failed to fetch OTT data.")

    ott_data_cache.clear()
    buttons = []

    for key in data:
        platform = data[key]["title"]
        movies = data[key].get("movies", [])
        if movies:
            ott_data_cache[platform] = movies
            buttons.append([KeyboardButton(platform)])

    reply_markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True, one_time_keyboard=True)
    await message.reply("🎬 *Select a platform to view what's streaming:*", reply_markup=reply_markup)

@Client.on_message(filters.text & ~filters.command("ott"))
async def platform_selected(client: Client, message: Message):
    platform = message.text.strip()
    if platform not in ott_data_cache:
        return

    user_id = message.from_user.id
    user_movie_state[user_id] = {"platform": platform, "page": 0}
    await show_movies(client, message.chat.id, user_id, message_id=None, edit=False)

async def show_movies(client, chat_id, user_id, message_id=None, edit=True):
    state = user_movie_state.get(user_id)
    if not state:
        return

    platform = state["platform"]
    page = state["page"]
    movies = ott_data_cache.get(platform, [])

    per_page = 8
    start = page * per_page
    end = start + per_page
    page_movies = movies[start:end]
    total_pages = (len(movies) - 1) // per_page + 1

    # Inline movie buttons
    keyboard = []
    for movie in page_movies:
        keyboard.append([InlineKeyboardButton(movie["title"], callback_data="noop")])

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Back", callback_data="ott_prev"))
    if end < len(movies):
        nav_row.append(InlineKeyboardButton("➡️ Next", callback_data="ott_next"))
    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([InlineKeyboardButton("🔙 Back to Main Menu", callback_data="ott_main")])

    logo_url = movies[0].get("platform_logo", "")
    caption = f"**🎥 Now Streaming on {platform}**\n\n[‎]({logo_url})"

    reply_markup = InlineKeyboardMarkup(keyboard)
    if edit and message_id:
        await client.edit_message_caption(
            chat_id=chat_id,
            message_id=message_id,
            caption=caption,
            reply_markup=reply_markup,
            parse_mode="markdown"
        )
    else:
        await client.send_photo(
            chat_id=chat_id,
            photo=logo_url,
            caption=caption,
            reply_markup=reply_markup,
            parse_mode="markdown"
        )

@Client.on_callback_query(filters.regex("ott_(prev|next)"))
async def paginate_movies(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id not in user_movie_state:
        return

    direction = callback_query.data.split("_")[1]
    if direction == "next":
        user_movie_state[user_id]["page"] += 1
    elif direction == "prev":
        user_movie_state[user_id]["page"] -= 1

    await show_movies(client, callback_query.message.chat.id, user_id, callback_query.message.message_id)

@Client.on_callback_query(filters.regex("ott_main"))
async def back_to_main(client: Client, callback_query: CallbackQuery):
    await ott_command(client, callback_query.message)

@Client.on_callback_query(filters.regex("noop"))
async def no_operation(client: Client, callback_query: CallbackQuery):
    await callback_query.answer("🎬 Just a title", show_alert=False)
