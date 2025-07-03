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

# Fetch all movies from all pages (no filtering)
def fetch_latest_movies():
    base_url = "https://www.binged.com/wp-json/binged-api/v1/movies?mode=streaming-week"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.121 Safari/537.36',
        'Referer': 'https://www.binged.com/'
    }

    all_movies = []
    current_page = 1

    while True:
        try:
            url = f"{base_url}&page={current_page}" if current_page > 1 else base_url
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                break

            data = response.json()
            page_movies = data.get('data', [])
            all_movies.extend(page_movies)

            pagination = data.get("pagination", {})
            total_pages = pagination.get("total_pages", 1)

            if current_page >= total_pages:
                break

            current_page += 1

        except Exception as e:
            print("Error while fetching movies:", e)
            break

    return all_movies

# Store paginated movie data per user
user_pages = {}

# /latest command handler
@Client.on_message(filters.command("latest"))
async def latest_movies_command(client, message):
    movies_data = fetch_latest_movies()
    if not movies_data:
        await message.reply_text("⚠️ No latest movies found or failed to fetch.")
        return

    # Prepare serial-numbered titles internally
    titles = [(i + 1, clean_text(movie.get("title", "Untitled"))) for i, movie in enumerate(movies_data)]

    user_id = message.from_user.id
    user_pages[user_id] = {
        "titles": titles,
        "page": 0,
        "placeholder_message_id": None
    }

    # Send initial message with header and keyboard
    reply_markup = build_movies_keyboard(titles, 0)
    msg = await message.reply("🎬 **Latest Streaming Movies:**", reply_markup=reply_markup)
    user_pages[user_id]["placeholder_message_id"] = msg.message_id

# Build keyboard layout for current page
def build_movies_keyboard(titles, page):
    page_size = 20
    start = page * page_size
    end = start + page_size
    current_titles = titles[start:end]

    keyboard = []
    row = []
    for idx, title in current_titles:
        row.append(KeyboardButton(title))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    nav_buttons = []
    if page > 0:
        nav_buttons.append(KeyboardButton("⬅️ Prev"))
    if end < len(titles):
        nav_buttons.append(KeyboardButton("➡️ Next"))
    if nav_buttons:
        keyboard.append(nav_buttons)

    keyboard.append([KeyboardButton("❌ Close")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Pagination navigation (clean - update keyboard only)
@Client.on_message(filters.text & filters.regex("^(⬅️ Prev|➡️ Next)$"))
async def paginate_movies(client, message):
    user_id = message.from_user.id
    if user_id not in user_pages:
        await message.delete()
        return

    current_page = user_pages[user_id]["page"]
    if message.text == "➡️ Next":
        user_pages[user_id]["page"] = current_page + 1
    elif message.text == "⬅️ Prev" and current_page > 0:
        user_pages[user_id]["page"] = current_page - 1

    await message.delete()

    titles = user_pages[user_id]["titles"]
    new_markup = build_movies_keyboard(titles, user_pages[user_id]["page"])

    # Edit the original message's keyboard (only if message still exists)
    placeholder_msg_id = user_pages[user_id].get("placeholder_message_id")
    if placeholder_msg_id:
        try:
            await client.edit_message_reply_markup(
                chat_id=message.chat.id,
                message_id=placeholder_msg_id,
                reply_markup=new_markup
            )
        except:
            # fallback: send a new message if editing fails
            await client.send_message(message.chat.id, reply_markup=new_markup)

# Close the reply keyboard
@Client.on_message(filters.text & filters.regex("^❌ Close$"))
async def close_keyboard(client, message):
    await message.delete()
    await client.send_message(message.chat.id, ".", reply_markup=ReplyKeyboardRemove())
