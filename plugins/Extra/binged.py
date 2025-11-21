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

# Search APIs
SEARCH_URL = "https://www.binged.com/wp-json/binged-api/v1/movies"
DETAIL_URL = "https://www.binged.com/wp-json/binged-api/v1/movie"

# JustWatch API for backdrop images
JUSTWATCH_API = "https://imdb.iamidiotareyoutoo.com/justwatch"

# IMDB API
IMDB_SEARCH_API = "https://imdb.iamidiotareyoutoo.com/search"
IMDB_DETAIL_API = "https://imdb.iamidiotareyoutoo.com/justwatch"

# Anti-403 Headers
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/85.0.4183.121 Safari/537.36',
    'Referer': 'https://www.binged.com/'
}

# Temporary Data Stores
temp.BINGED_RESULTS = {}   # user_id -> {movie_id: movie_data}
temp.IMDB_RESULTS = {}     # user_id -> {movie_id: movie_data}
temp.EDITING_POST = {}     # admin_id -> {movie_id, source}
temp.MOVIE_STATUS = {}     # movie_id -> 'upcoming' or 'released'

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

# Fetch backdrop image from JustWatch API
def get_justwatch_backdrop(movie_title):
    """
    Fetch backdrop image from JustWatch API based on movie title
    Returns backdrop URL or None
    """
    try:
        params = {'q': movie_title}
        response = requests.get(JUSTWATCH_API, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Check if we have description with image
        if data.get("short"):
            description = data["short"]
            if description.get("image"):
                backdrop_url = description["image"].get("url")
                if backdrop_url:
                    return backdrop_url
        
        return None
    except Exception as e:
        print(f"JustWatch API Error: {e}")
        return None

# Get similar movies with better logic
def get_similar_movies(movie_data, count=3):
    """
    Get similar movies, ensuring they are different from the current movie
    Returns list of similar movie titles
    """
    similar = movie_data.get("similar", [])
    current_title = clean_text(movie_data.get("post_title", "")).lower()
    current_id = str(movie_data.get("ID", ""))
    
    unique_similar = []
    seen_titles = set()
    
    for sim in similar:
        sim_title = clean_text(sim.get("title", ""))
        sim_id = str(sim.get("id", ""))
        sim_title_lower = sim_title.lower()
        
        # Skip if it's the same movie (by title or ID)
        if sim_title_lower == current_title or sim_id == current_id:
            continue
        
        # Skip if we've already added this title
        if sim_title_lower in seen_titles:
            continue
        
        seen_titles.add(sim_title_lower)
        unique_similar.append(sim)
        
        if len(unique_similar) >= count:
            break
    
    return unique_similar

# Build message for released movie
def build_released_message(movie_data, bot_username, source='binged'):
    if source == 'imdb':
        title = clean_text(movie_data.get("title", "Unknown"))
        year = movie_data.get("year", "N/A")
        movie_type = movie_data.get("type", "Movie").capitalize()
        
        # Languages with hashtags
        lang_tags = "#English"  # Default for IMDB
        
        # Genres
        genres = movie_data.get("genres", [])
        genre_str = ", ".join(genres) if genres else "N/A"
        
        # Platform
        platform_str = "N/A"
        
        # Runtime, Rating
        runtime = movie_data.get("runtime", "N/A")
        if runtime and runtime != "N/A":
            runtime = f"{runtime}m"
        rating = movie_data.get("rating", "N/A")
        
        # Cast
        cast = movie_data.get("cast", [])
        cast_str = ", ".join(cast[:5]) if cast else "N/A"
        
        # Plot
        plot = clean_text(movie_data.get("description", "No description available."))
        
        # Message construction with collapsible blockquote
        msg = f"✅ **{title}** · {year} · `{movie_type}`\n\n"
        msg += f"**>🉑 {lang_tags}\n"
        msg += f">🎭 {genre_str} · 📺 {platform_str}\n"
        msg += f">⏱️ {runtime} · ⭐ {rating}\n"
        msg += f">👥 {cast_str}\n"
        msg += f">\n"
        msg += f">__Plot:__\n"
        msg += f">{plot}**\n"
        msg += f" **@MooviDex** "
        
        image = movie_data.get("image", "")
        return msg, image
    
    else:  # binged
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
        msg += f" **@MooviDex** "
        
        return msg, image

# Build message for upcoming movie
def build_upcoming_message(movie_data, bot_username, source='binged'):
    if source == 'imdb':
        title = clean_text(movie_data.get("title", "Unknown"))
        year = movie_data.get("year", "N/A")
        movie_type = movie_data.get("type", "Movie").capitalize()
        
        # Languages
        lang_str = "English"  # Default for IMDB
        
        # Genres
        genres = movie_data.get("genres", [])
        genre_str = ", ".join(genres) if genres else "N/A"
        
        # Plot
        plot = clean_text(movie_data.get("description", "No description available."))
        
        # Distinct upcoming format with collapsible blockquote
        msg = f"🔔 **{title}** · {year} · `{movie_type}`\n\n"
        msg += f">**🚀 COMING SOON**\n"
        msg += f"🉑 {lang_str}\n"
        msg += f"🎭 {genre_str}\n\n"
        msg += f"**@MooviDex**"
        
        image = movie_data.get("image", "")
        return msg, image
    
    else:  # binged
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

# /imdbpost command
@Client.on_message(filters.command("imdbpost"))
async def imdb_search(client, message):
    if message.from_user.id not in ADMIN_IDS:
        return await message.reply_text("🚫 This command is for admins only.")
    if len(message.command) < 2:
        return await message.reply_text("Usage: /imdbpost <movie name>")

    query = " ".join(message.command[1:]).strip()

    try:
        params = {'q': query}  # Changed from 'query' to 'q'
        resp = requests.get(IMDB_SEARCH_API, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        return await message.reply_text(f"IMDB API error: {e}")

    results = data.get("description", [])
    if not results:
        return await message.reply_text("No results found.")

    temp.IMDB_RESULTS[message.from_user.id] = {}
    buttons = []
    
    for idx, movie in enumerate(results[:10]):  # Limit to 10 results
        movie_id = movie.get("#IMDB_ID", str(idx))
        title = movie.get("#TITLE", "Unknown")
        year = movie.get("#YEAR", "N/A")
        btn_text = f"{title} ({year})"
        temp.IMDB_RESULTS[message.from_user.id][movie_id] = movie
        buttons.append([InlineKeyboardButton(btn_text, callback_data=f"imdb_detail_{movie_id}")])
    
    buttons.append([InlineKeyboardButton("Close ❌", callback_data="close_message")])
    await message.reply_text(
        f"IMDB Search results for: <b>{query}</b>",
        reply_markup=InlineKeyboardMarkup(buttons),
        disable_web_page_preview=True
    )

# Show IMDB movie detail
@Client.on_callback_query(filters.regex(r"^imdb_detail_(.+)$"))
async def imdb_detail(client, cq):
    import re as regex_module  # Import with alias to avoid conflicts
    
    movie_id = cq.data.replace("imdb_detail_", "")
    user_id = cq.from_user.id
    
    # Get basic movie data from search results
    basic_data = temp.IMDB_RESULTS.get(user_id, {}).get(movie_id)
    if not basic_data:
        return await cq.answer("Movie data not found.", show_alert=True)
    
    title = basic_data.get("#TITLE", "Unknown")
    
    # Fetch detailed data from JustWatch API
    try:
        resp = requests.get(f"{JUSTWATCH_API}?q={title}", timeout=10)
        resp.raise_for_status()
        justwatch_data = resp.json()
    except:
        justwatch_data = {}
    
    # Merge data
    movie_data = {
        "title": title,
        "year": basic_data.get("#YEAR", "N/A"),
        "type": basic_data.get("#IMG_POSTER", "").split("/")[-2] if "#IMG_POSTER" in basic_data else "Movie",
        "image": basic_data.get("#IMG_POSTER", ""),
        "genres": [],
        "runtime": "N/A",
        "rating": "N/A",
        "cast": [],
        "description": "No description available."
    }
    
    # Extract data from JustWatch if available
    if justwatch_data.get("short"):
        short = justwatch_data["short"]
        movie_data["description"] = short.get("description", movie_data["description"])
        
        # Get image from JustWatch
        if short.get("image"):
            jw_image = short["image"].get("url")
            if jw_image:
                movie_data["image"] = jw_image
        
        # Get genres
        if short.get("genre"):
            movie_data["genres"] = short["genre"]
        
        # Get runtime (convert from minutes)
        if short.get("@type") == "Movie" and short.get("duration"):
            duration = short["duration"]
            # Duration is in ISO 8601 format like "PT120M"
            match = regex_module.search(r'PT(\d+)M', duration)
            if match:
                movie_data["runtime"] = match.group(1)
        
        # Get rating
        if short.get("aggregateRating"):
            rating = short["aggregateRating"].get("ratingValue")
            if rating:
                movie_data["rating"] = f"{rating}/10"
        
        # Get cast
        if short.get("actor"):
            actors = short["actor"]
            if isinstance(actors, list):
                movie_data["cast"] = [actor.get("name", "") for actor in actors]
    
    # Store full movie data
    temp.IMDB_RESULTS[user_id][movie_id] = movie_data
    
    safe_title = regex_module.sub(r'[^a-zA-Z0-9]', '_', title)
    year = movie_data.get("year", "N/A")
    
    # Ask admin to choose status
    buttons = [
        [
            InlineKeyboardButton("✅ Released", callback_data=f"imdb_status_released_{movie_id}"),
            InlineKeyboardButton("🔔 Upcoming", callback_data=f"imdb_status_upcoming_{movie_id}")
        ],
        [InlineKeyboardButton("❌ Close", callback_data="close_message")]
    ]
    
    preview_msg = f"**{title}** ({year})\n\nChoose movie status:"
    
    if movie_data["image"]:
        await cq.message.reply_photo(
            photo=movie_data["image"],
            caption=preview_msg,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    else:
        await cq.message.reply_text(
            preview_msg,
            reply_markup=InlineKeyboardMarkup(buttons),
            disable_web_page_preview=True
        )
    await cq.answer()

# Handle IMDB movie status selection
@Client.on_callback_query(filters.regex(r"^imdb_status_(released|upcoming)_(.+)$"))
async def imdb_status_select(client, cq):
    import re as regex_module  # Import with alias
    
    match = regex_module.match(r"^imdb_status_(released|upcoming)_(.+)$", cq.data)
    status = match.group(1)
    movie_id = match.group(2)
    user_id = cq.from_user.id
    
    movie_data = temp.IMDB_RESULTS.get(user_id, {}).get(movie_id)
    if not movie_data:
        return await cq.answer("Movie data not found.", show_alert=True)
    
    # Store status
    temp.MOVIE_STATUS[movie_id] = status
    
    title = clean_text(movie_data.get("title", "Unknown"))
    safe_title = regex_module.sub(r'[^a-zA-Z0-9]', '_', title)
    year = movie_data.get("year", "N/A")
    
    # Build message based on status
    if status == "upcoming":
        msg, image = build_upcoming_message(movie_data, temp.U_NAME, source='imdb')
    else:
        msg, image = build_released_message(movie_data, temp.U_NAME, source='imdb')
    
    # Build buttons based on status
    buttons = []
    
    if status == "released":
        # For released: Movie name button + more like this
        buttons.append([InlineKeyboardButton(
            f"{title} · {year}", 
            url=f"https://t.me/{temp.U_NAME}?start=Search_{safe_title}"
        )])
    
    # Admin buttons
    buttons.append([
        InlineKeyboardButton("✏️ Edit & Post", callback_data=f"imdb_edit_post_{movie_id}"),
        InlineKeyboardButton("📣 Post Default", callback_data=f"imdb_post_{movie_id}")
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

# Show Binged movie detail
@Client.on_callback_query(filters.regex(r"^binged_detail_(\d+)$"))
async def binged_detail(client, cq):
    import re as regex_module  # Import with alias
    
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
    safe_title = regex_module.sub(r'[^a-zA-Z0-9]', '_', title)
    year = movie_data.get("release_year", "N/A")
    
    # Ask admin to choose status
    buttons = [
        [
            InlineKeyboardButton("✅ Released", callback_data=f"binged_status_released_{movie_id}"),
            InlineKeyboardButton("🔔 Upcoming", callback_data=f"binged_status_upcoming_{movie_id}")
        ],
        [InlineKeyboardButton("❌ Close", callback_data="close_message")]
    ]
    
    preview_msg = f"**{title}** ({year})\n\nChoose movie status:"
    
    # Try to get backdrop from JustWatch API
    backdrop_image = get_justwatch_backdrop(title)
    final_image = backdrop_image if backdrop_image else movie_data.get("image", "")
    
    if final_image:
        await cq.message.reply_photo(
            photo=final_image,
            caption=preview_msg,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    else:
        await cq.message.reply_text(
            preview_msg,
            reply_markup=InlineKeyboardMarkup(buttons),
            disable_web_page_preview=True
        )
    await cq.answer()

# Handle Binged movie status selection
@Client.on_callback_query(filters.regex(r"^binged_status_(released|upcoming)_(\d+)$"))
async def binged_status_select(client, cq):
    import re as regex_module  # Import with alias
    
    match = regex_module.match(r"^binged_status_(released|upcoming)_(\d+)$", cq.data)
    status = match.group(1)
    movie_id = match.group(2)
    user_id = cq.from_user.id
    
    movie_data = temp.BINGED_RESULTS.get(user_id, {}).get(movie_id)
    if not movie_data:
        return await cq.answer("Movie data not found.", show_alert=True)
    
    # Store status
    temp.MOVIE_STATUS[movie_id] = status
    
    title = clean_text(movie_data.get("post_title", "Unknown"))
    safe_title = regex_module.sub(r'[^a-zA-Z0-9]', '_', title)
    year = movie_data.get("release_year", "N/A")
    
    # Build message based on status
    if status == "upcoming":
        msg, image = build_upcoming_message(movie_data, temp.U_NAME, source='binged')
    else:
        msg, image = build_released_message(movie_data, temp.U_NAME, source='binged')
    
    # Try to get backdrop from JustWatch API
    backdrop_image = get_justwatch_backdrop(title)
    final_image = backdrop_image if backdrop_image else image
    
    # Build buttons based on status
    buttons = []
    
    if status == "upcoming":
        # For upcoming: Only trailer button
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
        
        # Get unique similar movies
        similar_movies = get_similar_movies(movie_data, count=1)
        if similar_movies:
            similar_title = clean_text(similar_movies[0].get("title", ""))
            safe_similar = regex_module.sub(r'[^a-zA-Z0-9]', '_', similar_title)
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
    if final_image:
        await cq.message.reply_photo(
            photo=final_image,
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

# Post Binged movie directly to channel
@Client.on_callback_query(filters.regex(r"^binged_post_(\d+)$"))
async def binged_post(client, cq):
    import re as regex_module  # Import with alias
    
    if cq.from_user.id not in ADMIN_IDS:
        return await cq.answer("You're not authorized.", show_alert=True)
    movie_id = cq.data.split("_")[-1]
    movie_data = temp.BINGED_RESULTS.get(cq.from_user.id, {}).get(movie_id)
    if not movie_data:
        return await cq.answer("Movie data not found.", show_alert=True)

    title = clean_text(movie_data.get("post_title", "Unknown"))
    safe_title = regex_module.sub(r'[^a-zA-Z0-9]', '_', title)
    year = movie_data.get("release_year", "N/A")
    
    # Get status from temp storage
    status = temp.MOVIE_STATUS.get(movie_id, "released")
    
    if status == "upcoming":
        msg, image = build_upcoming_message(movie_data, temp.U_NAME, source='binged')
    else:
        msg, image = build_released_message(movie_data, temp.U_NAME, source='binged')
    
    # Try to get backdrop from JustWatch API
    backdrop_image = get_justwatch_backdrop(title)
    final_image = backdrop_image if backdrop_image else image
    
    # Build buttons based on status
    buttons = []
    
    if status == "upcoming":
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
        
        # Get unique similar movies
        similar_movies = get_similar_movies(movie_data, count=1)
        if similar_movies:
            similar_title = clean_text(similar_movies[0].get("title", ""))
            safe_similar = regex_module.sub(r'[^a-zA-Z0-9]', '_', similar_title)
            second_row.append(InlineKeyboardButton(
                "🔄 More like this", 
                url=f"https://t.me/{temp.U_NAME}?start=Search_{safe_similar}"
            ))
        
        if second_row:
            buttons.append(second_row)
    
    # Send to channel
    try:
        if final_image:
            await client.send_photo(
                chat_id=-1001680629032,
                photo=final_image,
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
    except Exception as e:
        await cq.answer(f"❌ Error posting: {e}", show_alert=True)

# Post IMDB movie directly to channel
@Client.on_callback_query(filters.regex(r"^imdb_post_(.+)$"))
async def imdb_post(client, cq):
    import re as regex_module  # Import with alias
    
    if cq.from_user.id not in ADMIN_IDS:
        return await cq.answer("You're not authorized.", show_alert=True)
    movie_id = cq.data.replace("imdb_post_", "")
    movie_data = temp.IMDB_RESULTS.get(cq.from_user.id, {}).get(movie_id)
    if not movie_data:
        return await cq.answer("Movie data not found.", show_alert=True)

    title = clean_text(movie_data.get("title", "Unknown"))
    safe_title = regex_module.sub(r'[^a-zA-Z0-9]', '_', title)
    year = movie_data.get("year", "N/A")
    
    # Get status from temp storage
    status = temp.MOVIE_STATUS.get(movie_id, "released")
    
    if status == "upcoming":
        msg, image = build_upcoming_message(movie_data, temp.U_NAME, source='imdb')
    else:
        msg, image = build_released_message(movie_data, temp.U_NAME, source='imdb')
    
    # Build buttons based on status
    buttons = []
    
    if status == "released":
        buttons.append([InlineKeyboardButton(
            f"{title} · {year}", 
            url=f"https://t.me/{temp.U_NAME}?start=Search_{safe_title}"
        )])
    
    # Send to channel
    try:
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
    except Exception as e:
        await cq.answer(f"❌ Error posting: {e}", show_alert=True)

# Prompt for custom button input (Binged)
@Client.on_callback_query(filters.regex(r"^binged_edit_post_(\d+)$"))
async def binged_edit_post_prompt(client, cq):
    movie_id = cq.data.split("_")[-1]
    user_id = cq.from_user.id
    temp.EDITING_POST[user_id] = {"movie_id": movie_id, "source": "binged"}

    await cq.message.reply_text("✏️ Send the **new search keyword** or **full URL** to use in the search button.", quote=True)
    await cq.answer()

# Prompt for custom button input (IMDB)
@Client.on_callback_query(filters.regex(r"^imdb_edit_post_(.+)$"))
async def imdb_edit_post_prompt(client, cq):
    movie_id = cq.data.replace("imdb_edit_post_", "")
    user_id = cq.from_user.id
    temp.EDITING_POST[user_id] = {"movie_id": movie_id, "source": "imdb"}

    await cq.message.reply_text("✏️ Send the **new search keyword** or **full URL** to use in the search button.", quote=True)
    await cq.answer()

# Handle admin reply with custom button
@Client.on_message(filters.private & filters.text & filters.user(ADMIN_IDS) & filters.create(lambda _, __, msg: msg.from_user.id in temp.EDITING_POST))
async def receive_custom_search(client, message):
    import re as regex_module  # Import with alias
    
    user_id = message.from_user.id
    custom_input = message.text.strip()

    if user_id not in temp.EDITING_POST:
        return

    edit_data = temp.EDITING_POST.pop(user_id)
    movie_id = edit_data["movie_id"]
    source = edit_data["source"]
    
    # Get movie data based on source
    if source == "binged":
        movie_data = temp.BINGED_RESULTS.get(user_id, {}).get(movie_id)
    else:  # imdb
        movie_data = temp.IMDB_RESULTS.get(user_id, {}).get(movie_id)
    
    if not movie_data:
        return await message.reply("❌ Movie session expired. Please search again.")

    # Get title based on source
    if source == "binged":
        title = clean_text(movie_data.get("post_title", "Unknown"))
        year = movie_data.get("release_year", "N/A")
    else:  # imdb
        title = clean_text(movie_data.get("title", "Unknown"))
        year = movie_data.get("year", "N/A")
    
    # Get status from temp storage
    status = temp.MOVIE_STATUS.get(movie_id, "released")
    
    if status == "upcoming":
        msg, image = build_upcoming_message(movie_data, temp.U_NAME, source=source)
    else:
        msg, image = build_released_message(movie_data, temp.U_NAME, source=source)

    # Try to get backdrop from JustWatch API
    if source == "binged":
        backdrop_image = get_justwatch_backdrop(title)
        final_image = backdrop_image if backdrop_image else image
    else:  # imdb already has image from justwatch
        final_image = image

    # Build buttons based on status
    buttons = []
    
    if status == "upcoming":
        # For upcoming: Only trailer (binged only)
        if source == "binged":
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
            keyword = regex_module.sub(r'[^a-zA-Z0-9]', '_', custom_input)
            button_url = f"https://t.me/{temp.U_NAME}?start=Search_{keyword}"

        buttons.append([InlineKeyboardButton(f"{title} · {year}", url=button_url)])
        
        if source == "binged":
            second_row = []
            videos = movie_data.get("videos", [])
            if videos and len(videos) > 0:
                video_url = videos[0].get("url", "")
                if video_url:
                    trailer_url = f"https://www.youtube.com/watch?v={video_url}"
                    second_row.append(InlineKeyboardButton("🎬 Trailer", url=trailer_url))
            
            # Get unique similar movies
            similar_movies = get_similar_movies(movie_data, count=1)
            if similar_movies:
                similar_title = clean_text(similar_movies[0].get("title", ""))
                safe_similar = regex_module.sub(r'[^a-zA-Z0-9]', '_', similar_title)
                second_row.append(InlineKeyboardButton(
                    "🔄 More like this", 
                    url=f"https://t.me/{temp.U_NAME}?start=Search_{safe_similar}"
                ))
            
            if second_row:
                buttons.append(second_row)

    # Send to channel
    try:
        if final_image:
            await client.send_photo(
                chat_id=-1001680629032,
                photo=final_image,
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
    except Exception as e:
        await message.reply(f"❌ Error posting: {e}")

# Close message handler
@Client.on_callback_query(filters.regex(r"^close_message$"))
async def close_message_callback(client, cq):
    try:
        await cq.message.delete()
    except:
        pass
    await cq.answer()
