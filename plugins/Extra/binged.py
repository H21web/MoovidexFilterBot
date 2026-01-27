import aiohttp
import re
import html
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from utils import temp
from info import *
from plugins.Extra.image_gen import generate_status_image

# Helper to format search title with Season numbering and Year
def format_search_title(title, year):
    if not title:
        return ""
    
    # Clean title first
    title = clean_text(title)
        
    # Replace "Season X" with "S0X" case insensitive
    # Use a lambda to handle the match group padding
    def season_repl(match):
        try:
            num = int(match.group(1))
            return f"S{num:02d}"
        except:
            return match.group(0)
            
    title = re.sub(r'(?i)Season\s+(\d+)', season_repl, title)
    
    # Replace non-alphanumeric with _
    safe_title = re.sub(r'[^a-zA-Z0-9]', '_', title)
    
    # Append year if valid
    if year and str(year).isdigit():
         safe_title = f"{safe_title}_{year}"
         
    return safe_title



# Helper for async requests
async def fetch_json(url, params=None, headers=None, timeout=10):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers, timeout=timeout) as resp:
                if resp.status != 200:
                    return None
                return await resp.json()
    except Exception as e:
        print(f"Fetch Error: {e}")
        return None

# TMDB API
TMDB_API_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_URL = "https://image.tmdb.org/t/p/original"

# List of Admin IDs
ADMIN_IDS = [1011394081, 7191327005]
UPDATE_CHANNEL_ID = -1001680629032

from database.users_chats_db import db
from database.stats_db import stats_db

from database.users_chats_db import db

# Search APIs
# Search APIs
SEARCH_URL = "https://api2.ottplay.com/api/search-service/v1.1/universal-search"
# DETAIL_URL = "https://www.binged.com/wp-json/binged-api/v1/movie"

# Anti-403 Headers
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/85.0.4183.121 Safari/537.36',
    'Referer': 'https://www.binged.com/'
}

# Temporary Data Stores
# Temporary Data Stores
temp.BINGED_RESULTS = {}   # user_id -> {movie_id: movie_data}
temp.TMDB_RESULTS = {}     # user_id -> {movie_id: movie_data}
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

# Extract platform name from URL or logo with proper None handling
def get_platform_name(platform_data):
    """Extract proper platform name from platform data"""
    if not platform_data:
        return "OTT"
    
    # Get ref_url and logo_url with None checks
    ref_url = platform_data.get("ref_url") or ""
    logo_url = platform_data.get("logo_url") or ""
    
    # Convert to lowercase safely
    ref_url = ref_url.lower() if ref_url else ""
    logo_url = logo_url.lower() if logo_url else ""
    
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

# Search TMDB (Supports Name or IMDB ID)
async def find_tmdb_id(query):
    try:
        # Check if query is IMDB ID
        if re.match(r'^tt\d+$', query):
            url = f"{TMDB_API_URL}/find/{query}"
            params = {
                "api_key": TMDB_API_KEY,
                "external_source": "imdb_id"
            }
            data = await fetch_json(url, params=params)
            if not data: return []
            
            # Combine results
            results = []
            for media_type in ["movie_results", "tv_results"]:
                for item in data.get(media_type, []):
                    item["media_type"] = "movie" if media_type == "movie_results" else "tv"
                    results.append(item)
            return results
            
        else:
            # Regular search
            return await search_tmdb(query)
            
    except Exception as e:
        print(f"TMDB Find Error: {e}")
        return []

# Search TMDB (Name only)
async def search_tmdb(query):
    try:
        url = f"{TMDB_API_URL}/search/multi"
        params = {
            "api_key": TMDB_API_KEY,
            "query": query,
            "language": "en-US",
            "page": 1,
            "include_adult": "true"
        }
        data = await fetch_json(url, params=params)
        if not data: return []
        
        results = []
        for item in data.get("results", []):
            if item.get("media_type") not in ["movie", "tv"]:
                continue
            results.append(item)
        return results
    except Exception as e:
        print(f"TMDB Search Error: {e}")
        return []

# Advanced Search TMDB (Specific Type & Year)
async def search_tmdb_advanced(query, year=None, media_type="movie"):
    try:
        endpoint = "tv" if media_type == "tv" else "movie"
        url = f"{TMDB_API_URL}/search/{endpoint}"
        
        params = {
            "api_key": TMDB_API_KEY,
            "query": query,
            "language": "en-US",
            "page": 1,
            "include_adult": "true"
        }
        
        if year and str(year).isdigit():
            if media_type == "tv":
                params["first_air_date_year"] = str(year)
            else:
                params["primary_release_year"] = str(year)
                
        data = await fetch_json(url, params=params)
        if not data: return []
        
        results = []
        for item in data.get("results", []):
            item["media_type"] = media_type # Enforce type from search
            results.append(item)
            
        return results
    except Exception as e:
        print(f"TMDB Advanced Search Error: {e}")
        # Fallback to general search if specific fails
        return await search_tmdb(f"{query} {year}" if year else query)

# Get TMDB Details
async def get_tmdb_details(tmdb_id, media_type="movie"):
    try:
        url = f"{TMDB_API_URL}/{media_type}/{tmdb_id}"
        params = {
            "api_key": TMDB_API_KEY,
            "language": "en-US",
            "append_to_response": "credits,videos,images,recommendations,similar"
        }
        data = await fetch_json(url, params=params)
        if not data: return None
        
        # Process data
        title = data.get("title") or data.get("name") or "Unknown"
        release_date = data.get("release_date") or data.get("first_air_date") or "N/A"
        year = release_date.split("-")[0] if release_date != "N/A" else "N/A"
        
        # Genres
        genres = [g["name"] for g in data.get("genres", [])]
        
        # Cast
        cast = [c["name"] for c in data.get("credits", {}).get("cast", [])[:5]]
        
        # Runtime
        runtime = data.get("runtime") or (data.get("episode_run_time")[0] if data.get("episode_run_time") else None)
        runtime_str = f"{runtime}m" if runtime else "N/A"
        
        # Rating
        rating = f"{round(data.get('vote_average', 0), 1)}/10"
        
        # Images (Backdrop preference)
        poster_path = data.get("poster_path")
        backdrop_path = data.get("backdrop_path")
        
        # Advanced Image Selection: Landscape with Title Preference
        images = data.get("images", {})
        backdrops = images.get("backdrops", [])
        
        best_backdrop = None
        
        if backdrops:
            # 1. Filter English backdrops (likely to contain English title)
            # Check for iso_639_1 == "en" OR "null" (sometimes titles are in null lang)
            # Prioritize "en" explicitly for titles
            english_backdrops = [b for b in backdrops if b.get("iso_639_1") == "en"]
            
            # 2. Sort by vote_count (popularity usually means better quality/relevance)
            english_backdrops.sort(key=lambda x: x.get("vote_count", 0), reverse=True)
            
            # 3. Also sort all backdrops by vote_count as fallback
            backdrops.sort(key=lambda x: x.get("vote_count", 0), reverse=True)
            
            # 4. Secondary filter: backdrops with no language (often high quality but risky)
            none_backdrops = [b for b in backdrops if b.get("iso_639_1") is None]
            none_backdrops.sort(key=lambda x: x.get("vote_count", 0), reverse=True)

            # Strategy: Best English -> Best None (if high vote) -> Best Overall
            if english_backdrops:
                best_backdrop = english_backdrops[0].get("file_path")
            elif none_backdrops and none_backdrops[0].get("vote_count", 0) > 5: # Only if decent votes
                 best_backdrop = none_backdrops[0].get("file_path")
            elif backdrops:
                best_backdrop = backdrops[0].get("file_path")
        
        # Fallback to default backdrop if no specific one found
        if not best_backdrop:
            best_backdrop = backdrop_path
            
        image_url = f"{TMDB_IMAGE_URL}{best_backdrop}" if best_backdrop else (f"{TMDB_IMAGE_URL}{poster_path}" if poster_path else "")
        
        # Similar
        similar = []
        recommendations = data.get("recommendations", {}).get("results", []) or data.get("similar", {}).get("results", [])
        for item in recommendations:
            if item.get("backdrop_path") or item.get("poster_path"):
                similar.append({
                    "id": item.get("id"),
                    "title": item.get("title") or item.get("name"),
                    "media_type": media_type # Assuming similar are same type
                })
                
        # Videos
        videos = []
        for v in data.get("videos", {}).get("results", []):
            if v.get("site") == "YouTube" and v.get("type") == "Trailer":
                videos.append(v)
                
        return {
            "id": data.get("id"),
            "title": title,
            "year": year,
            "plot": data.get("overview", "No description available."),
            "rating": rating,
            "genres": genres,
            "cast": cast,
            "runtime": runtime_str,
            "image": image_url,
            "type": "Movie" if media_type == "movie" else "Series",
            "release_date": release_date,
            "videos": videos,
            "similar": similar,
            "media_type": media_type,
            "original_data": data # Keep original data for deep diving if needed
        }
    except Exception as e:
        print(f"TMDB Details Error: {e}")
        return None



# Get similar movies with better logic
def get_similar_movies(movie_data, count=3):
    """
    Get similar movies, ensuring they are different from the current movie
    Returns list of similar movie titles
    """
    similar = movie_data.get("similar", [])
    current_title = clean_text(movie_data.get("post_title", movie_data.get("title", ""))).lower()
    current_id = str(movie_data.get("ID", movie_data.get("id", "")))
    
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
        
        # Platform - ONLY FIRST streaming platform with None checks
        platforms = movie_data.get("platform_logos", [])
        platform_str = "N/A"
        if platforms:
            for p in platforms:
                if p and p.get("rent_and_buy") == "0":  # Only streaming platforms
                    ref_url = p.get("ref_url") or ""
                    platform_name = get_platform_name(p)
                    if ref_url:
                        platform_str = f"[{platform_name}]({ref_url})"
                    else:
                        platform_str = platform_name
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

# /binged command (JustWatch API)
@Client.on_message(filters.command("binged"))
async def binged_search(client, message):
    if message.from_user.id not in ADMIN_IDS:
        return await message.reply_text("🚫 This command is for admins only.")
    if len(message.command) < 2:
        return await message.reply_text("Usage: /binged <movie name>")

    query = " ".join(message.command[1:]).strip()
    
    # New JustWatch API Endpoint
    url = f"https://imdb.iamidiotareyoutoo.com/justwatch?q={query}"

    try:
        data = await fetch_json(url, headers={'User-Agent': 'Mozilla/5.0'})
        if not data:
            return await message.reply_text(f"API Error.")
    except Exception as e:
        return await message.reply_text(f"API error: {e}")

    results = data.get("description", [])
        
    if not results:
        return await message.reply_text("No results found.")

    temp.BINGED_RESULTS[message.from_user.id] = {}
    buttons = []
    for item in results:
        title = clean_text(item.get("title"))
        if not title: continue
        
        # Use valid ID, prefer tmdbId if available for later lookup
        item_id = str(item.get("id")) # internal id like tm1599399
        
        year = item.get("year", "N/A")
        ctype = item.get("type", "MOVIE")
        
        btn_text = f"{title} ({year}) - {ctype}"
        
        # Store item for details
        temp.BINGED_RESULTS[message.from_user.id][item_id] = item
        buttons.append([InlineKeyboardButton(btn_text, callback_data=f"binged_detail_{item_id}")])

    buttons.append([InlineKeyboardButton("Close ❌", callback_data="close_message")])
    await message.reply_text(
        f"JustWatch Search results for: <b>{query}</b>",
        reply_markup=InlineKeyboardMarkup(buttons),
        disable_web_page_preview=True
    )

# /imdbpost command (Now uses TMDB)
@Client.on_message(filters.command("imdbpost"))
async def imdb_search(client, message):
    if message.from_user.id not in ADMIN_IDS:
        return await message.reply_text("🚫 This command is for admins only.")
    if len(message.command) < 2:
        return await message.reply_text("Usage: /imdbpost <movie name>")

    query = " ".join(message.command[1:]).strip()
    
    # Use find_tmdb_id to support IMDB ID or Name
    results = await find_tmdb_id(query)
    if not results:
        # Log search stats for no results
        try:
            await stats_db.add_search_log(query, message.from_user.id, 0, source='imdb')
        except Exception as e:
            print(f"Error logging imdb search: {e}")
        return await message.reply_text("No results found on TMDB.")
    
    # Log search stats for success
    try:
        await stats_db.add_search_log(query, message.from_user.id, len(results), source='imdb')
    except Exception as e:
        print(f"Error logging imdb search: {e}")

    temp.TMDB_RESULTS[message.from_user.id] = {}
    buttons = []
    
    for item in results[:10]:
        tmdb_id = str(item.get("id"))
        title = item.get("title") or item.get("name") or "Unknown"
        date = item.get("release_date") or item.get("first_air_date") or "N/A"
        year = date.split("-")[0] if date != "N/A" else "N/A"
        media_type = item.get("media_type", "movie")
        
        btn_text = f"{title} ({year}) - {media_type.upper()}"
        temp.TMDB_RESULTS[message.from_user.id][tmdb_id] = item
        buttons.append([InlineKeyboardButton(btn_text, callback_data=f"imdb_detail_{tmdb_id}_{media_type}")])
    
    buttons.append([InlineKeyboardButton("Close ❌", callback_data="close_message")])
    await message.reply_text(
        f"TMDB Search results for: <b>{query}</b>",
        reply_markup=InlineKeyboardMarkup(buttons),
        disable_web_page_preview=True
    )

# Show TMDB movie detail
@Client.on_callback_query(filters.regex(r"^imdb_detail_(\d+)_(.+)$"))
async def imdb_detail(client, cq):
    import re as regex_module
    
    match = regex_module.match(r"^imdb_detail_(\d+)_(.+)$", cq.data)
    tmdb_id = match.group(1)
    media_type = match.group(2)
    user_id = cq.from_user.id
    
    # Get details
    movie_data = await get_tmdb_details(tmdb_id, media_type)
    
    if not movie_data:
        return await cq.answer("Failed to fetch details from TMDB.", show_alert=True)
    
    # Map plot to description for compatibility
    movie_data["description"] = movie_data.get("plot", "")
    
    # Store full movie data
    temp.TMDB_RESULTS[user_id] = temp.TMDB_RESULTS.get(user_id, {}) # Ensure dict exists
    temp.TMDB_RESULTS[user_id][tmdb_id] = movie_data
    
    title = movie_data.get("title", "Unknown")
    year = movie_data.get("year", "N/A")
    
    # Ask admin to choose status
    buttons = [
        [
            InlineKeyboardButton("✅ Released", callback_data=f"imdb_status_released_{tmdb_id}"),
            InlineKeyboardButton("🔔 Upcoming", callback_data=f"imdb_status_upcoming_{tmdb_id}")
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

# Handle IMDB/TMDB movie status selection
@Client.on_callback_query(filters.regex(r"^imdb_status_(released|upcoming)_(.+)$"))
async def imdb_status_select(client, cq):
    import re as regex_module
    
    match = regex_module.match(r"^imdb_status_(released|upcoming)_(.+)$", cq.data)
    status = match.group(1)
    tmdb_id = match.group(2)
    user_id = cq.from_user.id
    
    movie_data = temp.TMDB_RESULTS.get(user_id, {}).get(tmdb_id)
    if not movie_data:
        return await cq.answer("Movie data not found.", show_alert=True)
    
    # Store status
    temp.MOVIE_STATUS[tmdb_id] = status
    
    title = clean_text(movie_data.get("title", "Unknown"))
    year = movie_data.get("year", "N/A")
    safe_title = format_search_title(title, year)
    
    # Build message based on status
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
    
        # Add Similar Movies Button
        similar_movies = movie_data.get("similar", [])
        if similar_movies:
            # similar is list of dicts {id, title, media_type}
            similar_title = clean_text(similar_movies[0].get("title", ""))
            safe_similar = format_search_title(similar_title, None)
            buttons.append([InlineKeyboardButton(
                "🔄 More like this", 
                url=f"https://t.me/{temp.U_NAME}?start=Search_{safe_similar}"
            )])

    # Admin buttons
    buttons.append([
        InlineKeyboardButton("✏️ Edit & Post", callback_data=f"imdb_edit_post_{tmdb_id}"),
        InlineKeyboardButton("📣 Post Default", callback_data=f"imdb_post_{tmdb_id}")
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

# Show JustWatch movie detail
@Client.on_callback_query(filters.regex(r"^binged_detail_(.+)$"))
async def binged_detail(client, cq):
    movie_id = cq.data.split("_")[-1]
    user_id = cq.from_user.id
    
    # Retrieve movie data from temp storage
    movie = temp.BINGED_RESULTS.get(user_id, {}).get(movie_id)
    
    if not movie:
         return await cq.answer("Movie details not found (cache expired). Search again.", show_alert=True)

    await cq.answer("Fetching details...")

    # Data from JustWatch
    title = clean_text(movie.get("title", ""))
    year = movie.get("year", "N/A")
    jw_type = movie.get("type", "MOVIE") 
    media_type = "movie" if jw_type == "MOVIE" else "tv"
    type_str = "Movie" if media_type == "movie" else "Series"
    
    # Providers from JustWatch
    offers = movie.get("offers", [])
    provider_logos = [] 
    
    platform_links = []
    seen_platforms = set()
    
    for offer in offers:
        p_name = offer.get("name")
        p_url = offer.get("url")
        if p_name and p_name not in seen_platforms:
             seen_platforms.add(p_name)
             platform_links.append(f"[{p_name}]({p_url})")

    provider_str = ", ".join(platform_links[:3]) if platform_links else "N/A"
    
    # Images from JustWatch
    posters = movie.get("photo_url", [])
    jw_poster = posters[0] if posters else None

    backdrops = movie.get("backdrops", [])
    jw_backdrop = backdrops[0] if backdrops else None
    
    # Fetch Data from TMDB for missing fields (Plot, Cast, Rating, Genres)
    tmdb_id = movie.get("tmdbId")
    
    tmdb_plot, tmdb_rating, genres, cast_str = "No description available.", "N/A", [], "N/A"
    tmdb_backdrop, tmdb_poster = None, None
    lang_tag = "#Unknown"

    if tmdb_id:
        tmdb_details = await get_tmdb_details(tmdb_id, media_type)
    else:
        # Search match
        tmdb_results = await search_tmdb_advanced(title, year=year, media_type=media_type)
        if tmdb_results:
             tmdb_id = tmdb_results[0].get("id")
             tmdb_details = await get_tmdb_details(tmdb_id, media_type)
        else:
             tmdb_details = None

    if tmdb_details:
        tmdb_plot = tmdb_details.get("plot")
        tmdb_rating = tmdb_details.get("rating")
        genres = tmdb_details.get("genres", [])
        cast = tmdb_details.get("cast", [])
        cast_str = ", ".join(cast[:5]) if cast else "N/A"
        
        # Language Logic
        t_orig = tmdb_details.get("original_data", {})
        spoken = t_orig.get("spoken_languages", [])
        if spoken:
             langs = [l.get("english_name") for l in spoken]
             # Filter duplicates and limit
             seen_langs = set()
             final_langs = []
             for l in langs:
                 if l not in seen_langs:
                     final_langs.append(l)
                     seen_langs.add(l)
             lang_tag = " ".join([f"#{l.replace(' ', '')}" for l in final_langs[:3]])
        else:
             # Fallback to original language code if no spoken info
             ol = t_orig.get("original_language", "en")
             lang_map = {"en": "English", "hi": "Hindi", "ta": "Tamil", "te": "Telugu", "ml": "Malayalam", "kn": "Kannada"}
             l_name = lang_map.get(ol, ol)
             lang_tag = f"#{l_name}"

        # Image Logic
        tmdb_img = tmdb_details.get("image")
        if tmdb_img: tmdb_backdrop = tmdb_img
        
        p_path = t_orig.get("poster_path")
        if p_path: tmdb_poster = f"https://image.tmdb.org/t/p/original{p_path}"
             
    genre_str = ", ".join(genres) if genres else "N/A"
    
    movie['rating'] = tmdb_rating
    movie['post_content'] = tmdb_plot
    movie['genre'] = genres
    movie['genre_str'] = genre_str
    movie['cast'] = cast
    movie['cast_str'] = cast_str
    movie['backdrop_url'] = jw_backdrop
    movie['poster_url'] = jw_poster
    movie['provider_logos'] = provider_logos if 'provider_logos' in locals() else []
    movie['image'] = tmdb_backdrop or jw_backdrop # Persist best image URL
    
    # Save back to temp
    temp.BINGED_RESULTS[user_id][movie_id] = movie

    msg = f"✅ **{title}** · {year} · `{type_str}`\n\n"
    msg += f"**>🉑 {lang_tag}\n"
    msg += f">🎭 {genre_str} · 📺 {provider_str}\n"
    msg += f">®️ N/A · ⭐ {tmdb_rating}\n" 
    msg += f">📅 {year}\n"
    msg += f">👥 {cast_str}\n"
    msg += f">\n"
    msg += f">__Plot:__\n"
    msg += f">{tmdb_plot}**\n"
    msg += f" **@MooviDex** "
    
    # Image Generation
    final_image_io = None
    if jw_backdrop and jw_poster:
         # Try/Except for image generation to be safe
         try:
            await cq.answer("Generating image...", cache_time=0)
            final_image_io = await generate_status_image(jw_backdrop, jw_poster, [], title, year, tmdb_rating, genre_str, tmdb_plot)
         except Exception as e:
            print(f"Image Gen Error: {e}")

    safe_title = format_search_title(title, year)
    buttons = [[InlineKeyboardButton(f"🔍 Search: {title}", url=f"https://t.me/{temp.U_NAME}?start=Search_{safe_title}")]]
    
    # Admin buttons
    buttons.append([
        InlineKeyboardButton("✏️ Edit & Post", callback_data=f"binged_edit_post_{movie_id}"),
        InlineKeyboardButton("📣 Post Default", callback_data=f"binged_post_{movie_id}")
    ])
    buttons.append([InlineKeyboardButton("❌ Close", callback_data="close_message")])
    
    if final_image_io:
        await cq.message.reply_photo(photo=final_image_io, caption=msg, reply_markup=InlineKeyboardMarkup(buttons))
    elif jw_backdrop:
        await cq.message.reply_photo(photo=jw_backdrop, caption=msg, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await cq.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(buttons), disable_web_page_preview=True)
    await cq.answer()
            


# Handle Binged movie status selection
@Client.on_callback_query(filters.regex(r"^binged_status_(released|upcoming)_(\d+)$"))
async def binged_status_select(client, cq):
    import re as regex_module
    
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
    year = movie_data.get("release_year", "N/A")
    safe_title = format_search_title(title, year)
    
    # Build message based on status
    if status == "upcoming":
        msg, image = build_upcoming_message(movie_data, temp.U_NAME, source='binged')
    else:
        msg, image = build_released_message(movie_data, temp.U_NAME, source='binged')
    
    # Use Binged poster
    final_image = image
    
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
        
        # Add Notify Button for Upcoming
        buttons.append([InlineKeyboardButton("🔔 Notify when Released", callback_data=f"notify_release_{movie_id}")])
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
            safe_similar = format_search_title(similar_title, None)
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
    import re as regex_module
    
    if cq.from_user.id not in ADMIN_IDS:
        return await cq.answer("You're not authorized.", show_alert=True)
    movie_id = cq.data.split("_")[-1]
    movie_data = temp.BINGED_RESULTS.get(cq.from_user.id, {}).get(movie_id)
    if not movie_data:
        return await cq.answer("Movie data not found.", show_alert=True)

    title = clean_text(movie_data.get("post_title", "Unknown"))
    year = movie_data.get("release_year", "N/A")
    safe_title = format_search_title(title, year)
    
    # Get status from temp storage
    status = temp.MOVIE_STATUS.get(movie_id, "released")
    
    if status == "upcoming":
        msg, image = build_upcoming_message(movie_data, temp.U_NAME, source='binged')
    else:
        msg, image = build_released_message(movie_data, temp.U_NAME, source='binged')
    
    # Use Binged poster
    final_image = image
    
    # Try to generate Image if components exist
    if movie_data.get('backdrop_url') and movie_data.get('poster_url'):
         try:
            await cq.answer("Generating image...", cache_time=0)
            final_image = await generate_status_image(
                movie_data['backdrop_url'], 
                movie_data['poster_url'], 
                movie_data.get('provider_logos', []), 
                title, 
                year, 
                movie_data.get('rating', 'N/A'), 
                movie_data.get('genre_str', 'N/A'), 
                movie_data.get('post_content', 'No plot')
            )
         except Exception as e:
            print(f"Post Image Gen Error: {e}")

    
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
        
        # Add Notify Button
        buttons.append([InlineKeyboardButton("🔔 Notify when Released", callback_data=f"notify_release_{movie_id}")])
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
                chat_id=UPDATE_CHANNEL_ID,
                photo=final_image,
                caption=msg,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        else:
            await client.send_message(
                chat_id=UPDATE_CHANNEL_ID,
                text=msg,
                reply_markup=InlineKeyboardMarkup(buttons),
                disable_web_page_preview=True
            )
        await cq.answer("✅ Posted to channel.")
    except Exception as e:
        await cq.answer(f"❌ Error posting: {e}", show_alert=True)

# Post IMDB/TMDB movie directly to channel
@Client.on_callback_query(filters.regex(r"^imdb_post_(.+)$"))
async def imdb_post(client, cq):
    import re as regex_module
    
    if cq.from_user.id not in ADMIN_IDS:
        return await cq.answer("You're not authorized.", show_alert=True)
    tmdb_id = cq.data.replace("imdb_post_", "")
    movie_data = temp.TMDB_RESULTS.get(cq.from_user.id, {}).get(tmdb_id)
    if not movie_data:
        return await cq.answer("Movie data not found.", show_alert=True)

    title = clean_text(movie_data.get("title", "Unknown"))
    safe_title = regex_module.sub(r'[^a-zA-Z0-9]', '_', title)
    year = movie_data.get("year", "N/A")
    
    # Get status from temp storage
    status = temp.MOVIE_STATUS.get(tmdb_id, "released")
    
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
        
        # Add Similar Movies Button
        similar_movies = movie_data.get("similar", [])
        if similar_movies:
            # similar is list of dicts {id, title, media_type}
            similar_title = clean_text(similar_movies[0].get("title", ""))
            safe_similar = regex_module.sub(r'[^a-zA-Z0-9]', '_', similar_title)
            buttons.append([InlineKeyboardButton(
                "🔄 More like this", 
                url=f"https://t.me/{temp.U_NAME}?start=Search_{safe_similar}"
            )])
    
    # Send to channel
    try:
        # Debug printing
        print(f"Posting to Channel ID: {UPDATE_CHANNEL_ID}")
        print(f"Image: {image}")
        
        if image:
            await client.send_photo(
                chat_id=UPDATE_CHANNEL_ID,
                photo=image,
                caption=msg,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        else:
            await client.send_message(
                chat_id=UPDATE_CHANNEL_ID,
                text=msg,
                reply_markup=InlineKeyboardMarkup(buttons),
                disable_web_page_preview=True
            )
        await cq.answer("✅ Posted to channel.")
    except Exception as e:
        print(f"Error Posting IMDB: {e}")
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
    import re as regex_module
    
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
    elif source == "ottplay":
        movie_data = getattr(temp, "OTTPLAY_RESULTS", {}).get(user_id, {}).get(movie_id)
    else:  # imdb
        movie_data = temp.TMDB_RESULTS.get(user_id, {}).get(movie_id)
    
    if not movie_data:
        return await message.reply("❌ Movie session expired. Please search again.")

    # Special Handling for Ottplay
    if source == "ottplay":
        data = movie_data
        is_upcoming = data.get('is_upcoming', False)
        emoji = "🔜" if is_upcoming else "✅"
        
        msg = f"{emoji} **{data['title']}** · {data['year']} · `{data['type_str']}`\n\n"
        msg += f"**>🉑 {data['lang_tag']}\n"
        
        if is_upcoming:
            msg += f">🎭 {data['genre_str']}\n"
            msg += f">🚀 **Releasing On:** {data['provider_str']}\n"
            msg += f">📅 **Date:** {data['r_date']}\n"
            msg += f">®️ {data['cert_str']} · ⭐ {data['rating']}\n"
        else:
            msg += f">🎭 {data['genre_str']} · 📺 {data['provider_str']}\n"
            msg += f">®️ {data['cert_str']} · ⭐ {data['rating']}\n"
            msg += f">📅 {data['r_date']}\n"

        msg += f">👥 {data['cast_str']}\n"
        msg += f">\n"
        msg += f">__Plot:__\n"
        msg += f">{data['plot']}**\n"
        msg += f" **@MooviDex** "
        
        final_image = None
        if data['backdrop_url'] and data['poster_url']:
            try:
                 final_image = await generate_status_image(
                    data['backdrop_url'], data['poster_url'], data['provider_logos'],
                    data['title'], data['year'], data['rating'], data['genre_str'], data['plot']
                 )
            except Exception as e:
                print(f"Edit Post Image Gen Error: {e}")
        
        if not final_image and data['backdrop_url']:
            final_image = data['backdrop_url']

        buttons = []
        
        # Notify Me for Upcoming (Priority)
        if is_upcoming:
             buttons.append([
                InlineKeyboardButton(f"🔔 Notify Me", callback_data=f"notify_{data['safe_title']}_{data['r_date']}")
            ])

        # Custom Button
        if custom_input.startswith("http://") or custom_input.startswith("https://"):
            button_url = custom_input
            buttons.append([InlineKeyboardButton(f"🔍 Search: {data['title']}", url=button_url)])
        else:
            safe_keyword = regex_module.sub(r'[^a-zA-Z0-9]', '_', custom_input)
            buttons.append([InlineKeyboardButton(
                f"🔍 Search: {data['title']}", 
                url=f"https://t.me/{temp.U_NAME}?start=Search_{safe_keyword}"
            )])
            
        row = []
        if data.get('trailer_url'):
            row.append(InlineKeyboardButton("🎬 Trailer", url=data['trailer_url']))
        if data.get('tmdb_id'):
            media_type = "movie" if data['type_str'] == "Movie" else "tv"
            row.append(InlineKeyboardButton("More like this", url=f"https://t.me/{temp.U_NAME}?start=more_like_{data['tmdb_id']}_{media_type}"))
        if row:
            buttons.append(row)

        try:
             if hasattr(final_image, 'seek'): final_image.seek(0)
             if final_image:
                 await client.send_photo(chat_id=UPDATE_CHANNEL_ID, photo=final_image, caption=msg, reply_markup=InlineKeyboardMarkup(buttons))
             else:
                 await client.send_message(chat_id=UPDATE_CHANNEL_ID, text=msg, reply_markup=InlineKeyboardMarkup(buttons), disable_web_page_preview=True)
             await message.reply("✅ Posted to channel with custom button.")
        except Exception as e:
             await message.reply(f"❌ Error posting: {e}")
        return

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

    # Use Binged poster
    if source == "binged":
        final_image = image
    else:  # imdb already has image from TMDB
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
                chat_id=UPDATE_CHANNEL_ID,
                photo=final_image,
                caption=msg,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        else:
            await client.send_message(
                chat_id=UPDATE_CHANNEL_ID,
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

# Handle Notify when Released
@Client.on_callback_query(filters.regex(r"^notify_release_(\d+)$"))
async def notify_release_callback(client, cq):
    movie_id = cq.data.split("_")[-1]
    user_id = cq.from_user.id
    
    # Add alert to DB
    await db.add_movie_alert(user_id, movie_id)
    await cq.answer("✅ Notification set! You will be notified when this movie releases.", show_alert=True)
    
    # Log to Log Channel
    try:
        # Try to get movie data from temp storage first
        movie_data = temp.BINGED_RESULTS.get(user_id, {}).get(movie_id)
        
        # If not found, fetch it
        if not movie_data:
             try:
                resp = await fetch_json(f"{DETAIL_URL}/{movie_id}", headers=HEADERS)
                if resp:
                    movie_data = resp
             except:
                pass
        
        if movie_data:
            title = clean_text(movie_data.get("post_title", "Unknown"))
            release_date = unix_to_date(movie_data.get("release_date"))
            subscribed_date = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
            user_link = f"<a href='tg://user?id={user_id}'>{cq.from_user.first_name}</a>"
            
            log_msg = (
                f"🔔 **New Notification Subscription**\n\n"
                f"👤 **User:** {user_link} (`{user_id}`)\n"
                f"🎬 **Movie:** {title}\n"
                f"📅 **Release Date:** {release_date}\n"
                f"⏰ **Subscribed Date:** {subscribed_date}"
            )
            
            if LOG_CHANNEL:
                await client.send_message(
                    chat_id=LOG_CHANNEL,
                    text=log_msg,
                    disable_web_page_preview=True
                )
    except Exception as e:
        print(f"Error logging notification: {e}")