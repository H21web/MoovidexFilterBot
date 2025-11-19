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
DETAIL_URL = "https://www.binged.com/wp-json/binged-api/v1/movie"

# Anti-403 Headers
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/85.0.4183.121 Safari/537.36',
    'Referer': 'https://www.binged.com/'
}

# Temporary Data Stores
temp.BINGED_RESULTS = {}   # user_id -> {movie_id: movie_data}
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

# Convert Unix timestamp to dd-mm-yyyy
def unix_to_date(unix_ts):
    try:
        return datetime.fromtimestamp(int(unix_ts)).strftime("%d-%m-%Y")
    except:
        return "N/A"

# Check if movie is upcoming (release date in future)
def is_upcoming(release_unix):
    try:
        release_date = datetime.fromtimestamp(int(release_unix))
        return release_date > datetime.now()
    except:
        return False

# Extract platform name from URL or logo
def get_platform_name(platform_data):
    """Extract proper platform name from platform data"""
    ref_url = platform_data.get("ref_url", "").lower()
    logo_url = platform_data.get("logo_url", "").lower()
    
    # Check ref_url and logo_url for platform identification
    if "hotstar" in ref_url or "hotstar" in logo_url:
        return "Hotstar"
    elif "primevideo" in ref_url or "prime" in ref_url or "primevideo" in logo_url or "prime" in logo_url:
        return "Prime Video"
    elif "netflix" in ref_url or "netflix" in logo_url:
        return "Netflix"
    elif "zee5" in ref_url or "zee5" in logo_url:
        return "Zee5"
    elif "sunnxt" in ref_url or "sunnxt" in logo_url:
        return "SunNXT"
    elif "sonyliv" in ref_url or "sonyliv" in logo_url:
        return "SonyLIV"
    elif "jiocinema" in ref_url or "jiocinema" in logo_url:
        return "JioCinema"
    elif "voot" in ref_url or "voot" in logo_url:
        return "Voot"
    elif "mxplayer" in ref_url or "mxplayer" in logo_url:
        return "MX Player"
    elif "aha" in ref_url or "aha" in logo_url:
        return "Aha"
    elif "apple" in ref_url or "appletv" in logo_url:
        return "Apple TV+"
    elif "hulu" in ref_url or "hulu" in logo_url:
        return "Hulu"
    elif "hbo" in ref_url or "hbo" in logo_url:
        return "HBO Max"
    elif "disney" in ref_url or "disney" in logo_url:
        return "Disney+"
    else:
        return "OTT"

# Build message for released movie
def build_released_message(movie_data, bot_username):
    title = clean_text(movie_data.get("post_title", "Unknown"))
    year = movie_data.get("release_year", "N/A")
    movie_type = movie_data.get("category", "N/A")
    image = movie_data.get("image", "")
    
    # Languages with hashtags
    langs = movie_data.get("lang", [])
    lang_tags = " ".join([f"#{lang.strip().replace(' ', '')}" for lang in langs]) if langs else "#Unknown"
    
    # Genres
    genres = movie_data.get("genre", [])
    genre_str = ", ".join(genres) if genres else "N/A"
    
    # Platform - ONLY FIRST streaming platform
    platforms = movie_data.get("platform_logos", [])
    platform_str = "N/A"
    for p in platforms:
        if p.get("rent_and_buy") == "0":  # Only streaming platforms
            ref_url = p.get("ref_url", "")
            platform_name = get_platform_name(p)
            platform_str = f"[{platform_name}]({ref_url})"
            break  # Take only the first platform
    
    # Runtime, Release Date, Censor
    runtime = movie_data.get("run_time", movie_data.get("duration", "N/A"))
    if runtime != "N/A" and not runtime.endswith("m"):
        runtime = f"{runtime}m"
    release_date = unix_to_date(movie_data.get("release_date"))
    censor = movie_data.get("censor", "NR")
    
    # Cast
    actors = movie_data.get("actors", [])
    cast_names = [actor[1] for actor in actors[:5] if len(actor) > 1]  # Top 5 cast
    cast_str = ", ".join(cast_names) if cast_names else "N/A"
    
    # Plot
    plot = clean_text(movie_data.get("post_content", "No description available."))
    
    # Message construction with collapsible blockquote
    msg = f"✅ **{title}** · {year} · `{movie_type}`\n\n"
    msg += f"**>🉑 {lang_tags}\n"
    msg += f">🎭 {genre_str} · 📺 {platform_str}\n"
    msg += f">⏱️ {runtime} · ®️ {censor}\n"
    msg += f">📅 {release_date}\n"
    msg += f">👥 {cast_str}\n"
    msg += f">\n"
    msg += f">__Plot:__\n"
    msg += f">{plot}**\n"
    msg += f"**@MooviDex**"
    
    return msg, image

# Build message for upcoming movie
def build_upcoming_message(movie_data, bot_username):
    title = clean_text(movie_data.get("post_title", "Unknown"))
    year = movie_data.get("release_year", "N/A")
    movie_type = movie_data.get("category", "N/A")
    image = movie_data.get("image", "")
    
    # Languages
    langs = movie_data.get("lang", [])
    lang_str = ", ".join(langs) if langs else "Unknown"
    
    # Release Date
    release_date = unix_to_date(movie_data.get("release_date"))
    
    # Genres
    genres = movie_data.get("genre", [])
    genre_str = ", ".join(genres) if genres else "N/A"
    
    # Plot
    plot = clean_text(movie_data.get("post_content", "No description available."))
    
    # Distinct upcoming format with collapsible blockquote
    msg = f"🔔 **{title}** · {year} · `{movie_type}`\n\n"
    msg += f">**🚀 COMING SOON**\n"
    msg += f"🗓️ Releases : {release_date}\n"
    msg += f"🉑 {lang_str}\n"
    msg += f"🎭 {genre_str}\n\n"
    msg += f"**@MooviDex**"
    
    return msg, image

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
    
    # Fetch detailed movie data
    try:
        resp = requests.get(f"{DETAIL_URL}/{movie_id}", headers=HEADERS, timeout=10)
        resp.raise_for_status()
        movie_data = resp.json()
    except requests.RequestException as e:
        return await cq.answer(f"Failed to fetch movie details: {e}", show_alert=True)
    
    if not movie_data or "ID" not in movie_data:
        return await cq.answer("Movie data not found.", show_alert=True)
    
    # Store full movie data
    temp.BINGED_RESULTS[user_id] = temp.BINGED_RESULTS.get(user_id, {})
    temp.BINGED_RESULTS[user_id][movie_id] = movie_data
    
    title = clean_text(movie_data.get("post_title", "Unknown"))
    safe_title = re.sub(r'[^a-zA-Z0-9]', '_', title)
    year = movie_data.get("release_year", "N/A")
    
    # Check if upcoming
    upcoming = is_upcoming(movie_data.get("release_date", 0))
    
    if upcoming:
        msg, image = build_upcoming_message(movie_data, temp.U_NAME)
    else:
        msg, image = build_released_message(movie_data, temp.U_NAME)
    
    # Build buttons based on movie status
    buttons = []
    
    if upcoming:
        # For upcoming: Only trailer button (no search, no more like this)
        videos = movie_data.get("videos", [])
        if videos and len(videos) > 0:
            video_url = videos[0].get("url", "")
            if video_url:
                trailer_url = f"https://www.youtube.com/watch?v={video_url}"
                buttons.append([InlineKeyboardButton("🎬 Trailer", url=trailer_url)])
    else:
        # For released: All buttons
        # First row: Movie name · Year button
        buttons.append([InlineKeyboardButton(
            f"{title} · {year}", 
            url=f"https://t.me/{temp.U_NAME}?start=Search_{safe_title}"
        )])
        
        # Second row: Trailer and More like this
        second_row = []
        videos = movie_data.get("videos", [])
        if videos and len(videos) > 0:
            video_url = videos[0].get("url", "")
            if video_url:
                trailer_url = f"https://www.youtube.com/watch?v={video_url}"
                second_row.append(InlineKeyboardButton("🎬 Trailer", url=trailer_url))
        
        similar = movie_data.get("similar", [])
        if similar and len(similar) > 0:
            similar_title = clean_text(similar[0].get("title", ""))
            safe_similar = re.sub(r'[^a-zA-Z0-9]', '_', similar_title)
            second_row.append(InlineKeyboardButton(
                "🔄 More like this", 
                url=f"https://t.me/{temp.U_NAME}?start=Search_{safe_similar}"
            ))
        
        if second_row:
            buttons.append(second_row)
    
    # Admin buttons
    if user_id in ADMIN_IDS:
        buttons.append([
            InlineKeyboardButton("✏️ Edit & Post", callback_data=f"binged_edit_post_{movie_id}"),
            InlineKeyboardButton("📣 Post Default", callback_data=f"binged_post_{movie_id}")
        ])
    buttons.append([InlineKeyboardButton("❌ Close", callback_data="close_message")])
    
    # Send with image
    if image:
        await cq.message.reply_photo(
            photo=image,
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
    movie_data = temp.BINGED_RESULTS.get(cq.from_user.id, {}).get(movie_id)
    if not movie_data:
        return await cq.answer("Movie data not found.", show_alert=True)

    title = clean_text(movie_data.get("post_title", "Unknown"))
    safe_title = re.sub(r'[^a-zA-Z0-9]', '_', title)
    year = movie_data.get("release_year", "N/A")
    
    upcoming = is_upcoming(movie_data.get("release_date", 0))
    
    if upcoming:
        msg, image = build_upcoming_message(movie_data, temp.U_NAME)
    else:
        msg, image = build_released_message(movie_data, temp.U_NAME)
    
    # Build buttons based on movie status
    buttons = []
    
    if upcoming:
        # For upcoming: Only trailer
        videos = movie_data.get("videos", [])
        if videos and len(videos) > 0:
            video_url = videos[0].get("url", "")
            if video_url:
                trailer_url = f"https://www.youtube.com/watch?v={video_url}"
                buttons.append([InlineKeyboardButton("🎬 Trailer", url=trailer_url)])
    else:
        # For released: All buttons
        buttons.append([InlineKeyboardButton(
            f"{title} · {year}", 
            url=f"https://t.me/{temp.U_NAME}?start=Search_{safe_title}"
        )])
        
        second_row = []
        videos = movie_data.get("videos", [])
        if videos and len(videos) > 0:
            video_url = videos[0].get("url", "")
            if video_url:
                trailer_url = f"https://www.youtube.com/watch?v={video_url}"
                second_row.append(InlineKeyboardButton("🎬 Trailer", url=trailer_url))
        
        similar = movie_data.get("similar", [])
        if similar and len(similar) > 0:
            similar_title = clean_text(similar[0].get("title", ""))
            safe_similar = re.sub(r'[^a-zA-Z0-9]', '_', similar_title)
            second_row.append(InlineKeyboardButton(
                "🔄 More like this", 
                url=f"https://t.me/{temp.U_NAME}?start=Search_{safe_similar}"
            ))
        
        if second_row:
            buttons.append(second_row)
    
    # Send to channel
    if image:
        await client.send_photo(
            chat_id=-1001680629032,
            photo=image,
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
    movie_data = temp.BINGED_RESULTS.get(user_id, {}).get(movie_id)
    if not movie_data:
        return await message.reply("❌ Movie session expired. Please search again.")

    title = clean_text(movie_data.get("post_title", "Unknown"))
    year = movie_data.get("release_year", "N/A")
    
    upcoming = is_upcoming(movie_data.get("release_date", 0))
    
    if upcoming:
        msg, image = build_upcoming_message(movie_data, temp.U_NAME)
    else:
        msg, image = build_released_message(movie_data, temp.U_NAME)

    # Build buttons based on movie status
    buttons = []
    
    if upcoming:
        # For upcoming: Only trailer
        videos = movie_data.get("videos", [])
        if videos and len(videos) > 0:
            video_url = videos[0].get("url", "")
            if video_url:
                trailer_url = f"https://www.youtube.com/watch?v={video_url}"
                buttons.append([InlineKeyboardButton("🎬 Trailer", url=trailer_url)])
    else:
        # For released: Custom button + trailer + more like this
        # Decide URL for first button
        if custom_input.startswith("http://") or custom_input.startswith("https://"):
            button_url = custom_input
        else:
            keyword = re.sub(r'[^a-zA-Z0-9]', '_', custom_input)
            button_url = f"https://t.me/{temp.U_NAME}?start=Search_{keyword}"

        buttons.append([InlineKeyboardButton(f"{title} · {year}", url=button_url)])
        
        second_row = []
        videos = movie_data.get("videos", [])
        if videos and len(videos) > 0:
            video_url = videos[0].get("url", "")
            if video_url:
                trailer_url = f"https://www.youtube.com/watch?v={video_url}"
                second_row.append(InlineKeyboardButton("🎬 Trailer", url=trailer_url))
        
        similar = movie_data.get("similar", [])
        if similar and len(similar) > 0:
            similar_title = clean_text(similar[0].get("title", ""))
            safe_similar = re.sub(r'[^a-zA-Z0-9]', '_', similar_title)
            second_row.append(InlineKeyboardButton(
                "🔄 More like this", 
                url=f"https://t.me/{temp.U_NAME}?start=Search_{safe_similar}"
            ))
        
        if second_row:
            buttons.append(second_row)

    # Send to channel
    if image:
        await client.send_photo(
            chat_id=-1001680629032,
            photo=image,
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
    await message.reply("✅ Posted to channel with custom button.")

# Close message handler
@Client.on_callback_query(filters.regex(r"^close_message$"))
async def close_message_callback(client, cq):
    try:
        await cq.message.delete()
    except:
        pass
    await cq.answer()
