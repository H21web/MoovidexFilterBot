import requests
import re
import html
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from utils import temp
from info import *

# List of Admin IDs
ADMIN_IDS = [1011394081, 7191327005]

# Search API
SEARCH_URL = "https://www.binged.com/wp-json/binged-api/v1/movies"
MOVIE_DETAIL_URL = "https://www.binged.com/wp-json/binged-api/v1/movie/{}"

# Anti-403 Headers
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/85.0.4183.121 Safari/537.36',
    'Referer': 'https://www.binged.com/'
}

# Temporary Data Stores
temp.BINGED_RESULTS = {}  # user_id -> {movie_id: movie_data}
temp.EDITING_POST = {}  # admin_id -> movie_id

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
        val = clean_text(str(val)) if val else ""
        if val:
            result.append(val)
    return result

# Convert Unix timestamp to dd-mm-yyyy
def unix_to_date(timestamp):
    try:
        return datetime.fromtimestamp(int(timestamp)).strftime('%d-%m-%Y')
    except:
        return "N/A"

# Check if movie is upcoming (not released yet)
def is_upcoming(release_date_unix):
    try:
        current_time = datetime.now().timestamp()
        return int(release_date_unix) > current_time
    except:
        return False

# Generate movie message for released movies
def build_movie_message(data, bot_username):
    title = clean_text(data.get("post_title", "Unknown"))
    year = data.get("release_year", "N/A")
    category = clean_text(data.get("category", "Film"))
    
    # Languages with hashtags
    languages = data.get("lang", [])
    lang_str = " ".join([f"#{lang.replace(' ', '')}" for lang in languages]) if languages else "#NA"
    
    # Genres
    genres = data.get("genre", [])
    genre_str = " · ".join(genres) if genres else "N/A"
    
    # Platform with link
    platforms = data.get("platform_logos", [])
    platform_name = "N/A"
    platform_link = ""
    if platforms:
        platform_name = "Streaming"
        platform_link = platforms[0].get("ref_url", "")
    
    # Runtime
    runtime = data.get("run_time", "N/A")
    
    # Release date
    release_date_unix = data.get("release_date", "")
    release_date = unix_to_date(release_date_unix)
    
    # Censor rating
    censor = data.get("censor", "NR")
    
    # Cast names only
    actors = data.get("actors", [])
    cast_names = [actor[1] for actor in actors if isinstance(actor, list) and len(actor) > 1]
    cast_str = ", ".join(cast_names[:5]) if cast_names else "N/A"
    
    # Plot
    plot = clean_text(data.get("post_content", "No description available."))
    
    # Platform display with or without link
    if platform_link:
        platform_display = f"[{platform_name}]({platform_link})"
    else:
        platform_display = platform_name
    
    # Build message with blockquote
    safe_title = re.sub(r'[^a-zA-Z0-9]', '_', title)
    
    msg = f"**{title}** · {year} · {category}\n\n"
    msg += f">||🉑 {lang_str}\n"
    msg += f">||🎭 {genre_str} · 📺 {platform_display}\n"
    msg += f">||⏱️ {runtime} · 📅 {release_date} · 🎬 {censor}\n"
    msg += f">||👥 {cast_str}\n"
    msg += f">||__Plot:__ {plot}||\n\n"
    msg += f"**@MooviDex**"
    
    return msg, safe_title

# Generate minimal upcoming movie message
def build_upcoming_message(data, bot_username):
    title = clean_text(data.get("post_title", "Unknown"))
    year = data.get("release_year", "N/A")
    category = clean_text(data.get("category", "Film"))
    
    # Theatre/Release date
    theatre_date_unix = data.get("theatre_date", data.get("release_date", ""))
    theatre_date = unix_to_date(theatre_date_unix)
    
    safe_title = re.sub(r'[^a-zA-Z0-9]', '_', title)
    
    msg = f"🔜 **UPCOMING**\n\n"
    msg += f"**{title}** · {year} · {category}\n"
    msg += f"📅 Releasing: {theatre_date}\n\n"
    msg += f"**@MooviDex**"
    
    return msg, safe_title

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
        f"Search results for: {query}",
        reply_markup=InlineKeyboardMarkup(buttons),
        disable_web_page_preview=True
    )

# Show movie detail with full API data
@Client.on_callback_query(filters.regex(r"^binged_detail_(\d+)$"))
async def binged_detail(client, cq):
    movie_id = cq.data.split("_")[-1]
    user_id = cq.from_user.id
    
    movie = temp.BINGED_RESULTS.get(user_id, {}).get(movie_id)
    if not movie:
        return await cq.answer("Session expired. Please search again.", show_alert=True)
    
    # Fetch full movie details from the detailed API
    try:
        detail_resp = requests.get(MOVIE_DETAIL_URL.format(movie_id), headers=HEADERS, timeout=10)
        detail_resp.raise_for_status()
        movie_data = detail_resp.json()
    except requests.RequestException as e:
        return await cq.answer(f"Failed to fetch movie details: {e}", show_alert=True)
    
    # Check if upcoming or released
    release_date_unix = movie_data.get("release_date", "")
    upcoming = is_upcoming(release_date_unix)
    
    if upcoming:
        msg, safe_title = build_upcoming_message(movie_data, temp.U_NAME)
    else:
        msg, safe_title = build_movie_message(movie_data, temp.U_NAME)
    
    # Get movie poster
    image_url = movie_data.get("image", "")
    
    # Get trailer URL
    videos = movie_data.get("videos", [])
    trailer_url = None
    if videos:
        trailer_id = videos[0].get("url", "")
        if trailer_id:
            trailer_url = f"https://www.youtube.com/watch?v={trailer_id}"
    
    # Get similar movies
    similar = movie_data.get("similar", [])
    
    # Build inline buttons
    title = clean_text(movie_data.get("post_title", "Unknown"))
    year = movie_data.get("release_year", "N/A")
    
    buttons = []
    
    # First row: Movie name · Year (search button)
    buttons.append([InlineKeyboardButton(f"{title} · {year}", url=f"https://t.me/{temp.U_NAME}?start=Search_{safe_title}")])
    
    # Second row: Trailer and More like this
    second_row = []
    if trailer_url:
        second_row.append(InlineKeyboardButton("🎬 Trailer", url=trailer_url))
    if similar:
        # Use first similar movie for "More like this"
        similar_title = similar[0].get("title", "similar")
        safe_similar = re.sub(r'[^a-zA-Z0-9]', '_', similar_title)
        second_row.append(InlineKeyboardButton("🎞️ More like this", url=f"https://t.me/{temp.U_NAME}?start=Search_{safe_similar}"))
    
    if second_row:
        buttons.append(second_row)
    
    # Admin buttons
    if user_id in ADMIN_IDS:
        buttons.append([
            InlineKeyboardButton("✏️ Edit & Post", callback_data=f"binged_edit_post_{movie_id}"),
            InlineKeyboardButton("📣 Post Default", callback_data=f"binged_post_{movie_id}")
        ])
    
    buttons.append([InlineKeyboardButton("❌ Close", callback_data="close_message")])
    
    # Send with image if available
    if image_url:
        await cq.message.reply_photo(
            photo=image_url,
            caption=msg,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    else:
        await cq.message.reply_text(
            msg,
            reply_markup=InlineKeyboardMarkup(buttons),
            disable_web_page_preview=True
        )
    
    await cq.answer()

# Post directly to channel
@Client.on_callback_query(filters.regex(r"^binged_post_(\d+)$"))
async def binged_post(client, cq):
    if cq.from_user.id not in ADMIN_IDS:
        return await cq.answer("You're not authorized.", show_alert=True)
    
    movie_id = cq.data.split("_")[-1]
    
    # Fetch full movie details
    try:
        detail_resp = requests.get(MOVIE_DETAIL_URL.format(movie_id), headers=HEADERS, timeout=10)
        detail_resp.raise_for_status()
        movie_data = detail_resp.json()
    except requests.RequestException as e:
        return await cq.answer(f"Failed to fetch movie details: {e}", show_alert=True)
    
    # Check if upcoming or released
    release_date_unix = movie_data.get("release_date", "")
    upcoming = is_upcoming(release_date_unix)
    
    if upcoming:
        msg, safe_title = build_upcoming_message(movie_data, temp.U_NAME)
    else:
        msg, safe_title = build_movie_message(movie_data, temp.U_NAME)
    
    # Get movie poster
    image_url = movie_data.get("image", "")
    
    # Get trailer URL
    videos = movie_data.get("videos", [])
    trailer_url = None
    if videos:
        trailer_id = videos[0].get("url", "")
        if trailer_id:
            trailer_url = f"https://www.youtube.com/watch?v={trailer_id}"
    
    # Get similar movies
    similar = movie_data.get("similar", [])
    
    # Build inline buttons
    title = clean_text(movie_data.get("post_title", "Unknown"))
    year = movie_data.get("release_year", "N/A")
    
    buttons = []
    buttons.append([InlineKeyboardButton(f"{title} · {year}", url=f"https://t.me/{temp.U_NAME}?start=Search_{safe_title}")])
    
    second_row = []
    if trailer_url:
        second_row.append(InlineKeyboardButton("🎬 Trailer", url=trailer_url))
    if similar:
        similar_title = similar[0].get("title", "similar")
        safe_similar = re.sub(r'[^a-zA-Z0-9]', '_', similar_title)
        second_row.append(InlineKeyboardButton("🎞️ More like this", url=f"https://t.me/{temp.U_NAME}?start=Search_{safe_similar}"))
    
    if second_row:
        buttons.append(second_row)
    
    # Send to channel
    if image_url:
        await client.send_photo(
            chat_id=-1001680629032,
            photo=image_url,
            caption=msg,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    else:
        await client.send_message(
            chat_id=-1001680629032,
            text=msg,
            reply_markup=InlineKeyboardMarkup(buttons),
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
@Client.on_message(filters.private & filters.text & filters.user(ADMIN_IDS) & filters.create(lambda _, __, msg: msg.from_user.id in temp.EDITING_POST))
async def receive_custom_search(client, message):
    user_id = message.from_user.id
    custom_input = message.text.strip()
    
    if user_id not in temp.EDITING_POST:
        return
    
    movie_id = temp.EDITING_POST.pop(user_id)
    
    # Fetch full movie details
    try:
        detail_resp = requests.get(MOVIE_DETAIL_URL.format(movie_id), headers=HEADERS, timeout=10)
        detail_resp.raise_for_status()
        movie_data = detail_resp.json()
    except requests.RequestException as e:
        return await message.reply(f"❌ Failed to fetch movie details: {e}")
    
    # Check if upcoming or released
    release_date_unix = movie_data.get("release_date", "")
    upcoming = is_upcoming(release_date_unix)
    
    if upcoming:
        msg, safe_title = build_upcoming_message(movie_data, temp.U_NAME)
    else:
        msg, safe_title = build_movie_message(movie_data, temp.U_NAME)
    
    # Get movie poster
    image_url = movie_data.get("image", "")
    
    # Decide URL
    if custom_input.startswith("http://") or custom_input.startswith("https://"):
        button_url = custom_input
    else:
        keyword = re.sub(r'[^a-zA-Z0-9]', '_', custom_input)
        button_url = f"https://t.me/{temp.U_NAME}?start=Search_{keyword}"
    
    title = clean_text(movie_data.get("post_title", "Unknown"))
    year = movie_data.get("release_year", "N/A")
    
    # Send to channel
    if image_url:
        await client.send_photo(
            chat_id=-1001680629032,
            photo=image_url,
            caption=msg,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"{title} · {year}", url=button_url)]
            ])
        )
    else:
        await client.send_message(
            chat_id=-1001680629032,
            text=msg,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"{title} · {year}", url=button_url)]
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
