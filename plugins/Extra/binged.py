import requests
import re
import html
import asyncio
import sys
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from utils import temp
from info import *

# List of Admin IDs
ADMIN_IDS = [1011394081, 7191327005]

# Search APIs
SEARCH_URL = "https://www.binged.com/wp-json/binged-api/v1/movies"
TMDB_API_KEY = "eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiJiM2QxMGRhYjhlODI1MjVlM2EyZWQ4ZWQ4YmMzODg3NCIsIm5iZiI6MTY1MDU2MzgxNC41MzcsInN1YiI6IjYyNjE5YWU2NWE5OTE1MDA2NTI3YTE0ZCIsInNjb3BlcyI6WyJhcGlfcmVhZCJdLCJ2ZXJzaW9uIjoxfQ.n-NLP1s0rYpeT9Vp8pvhklckwInKnIjZSyC0oWo2BRM"  # Add your TMDB API key
TMDB_SEARCH_URL = "https://api.themoviedb.org/3/search/movie"
TMDB_TV_SEARCH_URL = "https://api.themoviedb.org/3/search/tv"

# Channel configuration
CHANNELS = [int(x) for x in getattr(sys.modules[__name__], 'CHANNELS', '').split() if x.strip()]
UPDATE_CHANNEL = -1001680629032  # Your update channel ID

# Anti-403 Headers
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/85.0.4183.121 Safari/537.36',
    'Referer': 'https://www.binged.com/'
}

# Temporary Data Stores
temp.BINGED_RESULTS = {}
temp.BINGED_STYLE = {}
temp.EDITING_POST = {}
temp.POSTED_MOVIES = set()  # Track posted movies to avoid duplicates

# Existing utility functions (keeping all your original functions)
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

def extract_list(data, key, nested_key=None):
    items = data.get(key)
    if not isinstance(items, list):
        return []
    result = []
    for i in items:
        val = i.get(nested_key) if nested_key and isinstance(i, dict) else i
        val = clean_text(val)
        if val:
            result.append(val)
    return result

def build_binged_message(title, year, movie_type, lang, genres, platform, style, safe_title, bot_username):
    lang_tag = ", ".join(f"#{l.strip().title()}" for l in lang) if isinstance(lang, list) else f"#{lang.strip().title()}" if lang else "N/A"
    genre_str = ", ".join(genres) or "N/A"
    movie_url = f"https://t.me/{bot_username}?start=Search_{safe_title}"
    
    if style == 1:
        return (
            f"✅ **{title}** · ({year}) · `{movie_type}`\n\n"
            f"🉑 {lang_tag}\n"
            f"🎭 {genre_str} · 📺 {platform}\n\n"
            f"**@MooviDex**"
        )
    elif style == 2:
        return (
            f"🎬 **[{title}]({movie_url})**\n"
            f"`───────────────`\n"
            f"📆 {year} · `{movie_type}`\n\n"
            f"🗣️ Language: {lang_tag}\n"
            f"🎭 Genre: {genre_str}\n"
            f"📺 Platform: {platform}\n\n"
            f"📡 **@MooviDex**"
        )
    elif style == 3:
        return (
            f"✅ **[{title}]({movie_url})**\n"
            f"`({year} · {movie_type})`\n\n"
            f"{lang_tag} 🎭 {genre_str} · 📺 {platform}\n\n"
            f"**@MooviDex**"
        )
    elif style == 4:
        return (
            f"🎬 **[{title}]({movie_url})**\n"
            f"`({year} · {movie_type})`\n\n"
            f"🉑 Language: {lang_tag}\n"
            f"🎭 Genres: {genre_str}\n"
            f"📺 Streaming On: {platform}\n\n"
            f"📝 *A compelling drama series.*\n\n"
            f"📢 Powered by **@MooviDex**"
        )
    elif style == 5:
        return (
            f"✨ **[{title}]({movie_url})**\n"
            f"`({year} · {movie_type})`\n\n"
            f"{lang_tag} 🎭 {genre_str}\n"
            f"📺 {platform}\n\n"
            f"🔥 Only on **@MooviDex**"
        )
    
    return f"✅ **[{title}]({movie_url})** · `({year}) · {movie_type}`\n\n🉑 {lang_tag}\n🎭 {genre_str} · 📺 {platform}\n**@MooviDex**"

# NEW FUNCTIONS FOR AUTO-UPDATE

def extract_movie_info_from_filename(filename):
    """Extract movie title and year from filename"""
    # Remove file extension
    name = re.sub(r'\.[^.]+$', '', filename)
    
    # Common patterns for movie files
    patterns = [
        r'^(.+?)[\.\s]+(\d{4})[\.\s]',  # Title.Year or Title Year
        r'^(.+?)[\.\s]*\((\d{4})\)',    # Title (Year)
        r'^(.+?)[\-\s]+(\d{4})',        # Title - Year
        r'^(.+?)_(\d{4})',              # Title_Year
    ]
    
    for pattern in patterns:
        match = re.search(pattern, name, re.IGNORECASE)
        if match:
            title = match.group(1).replace('.', ' ').replace('_', ' ').strip()
            year = int(match.group(2))
            return title, year
    
    # If no year found, try to extract just the title
    title = re.sub(r'[\.\-_]+', ' ', name)
    title = re.sub(r'\b\d{3,4}p\b|\bBluRay\b|\bWEB-?DL\b|\bHDRip\b|\bx26[45]\b|\bHEVC\b|\bDDP?\d+\.\d+\b|\b10bit\b', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\s+', ' ', title).strip()
    
    return title, None

async def search_binged_api(query, max_retries=3):
    """Enhanced Binged API search with retry logic"""
    for attempt in range(max_retries):
        try:
            # Clean query for better search results
            clean_query = re.sub(r'[^\w\s]', ' ', query).strip()
            
            resp = requests.get(
                f"{SEARCH_URL}?mode=all&search={clean_query}", 
                headers=HEADERS, 
                timeout=15
            )
            resp.raise_for_status()
            
            data = resp.json()
            results = data.get("data", [])
            
            if results:
                return results
                
        except requests.RequestException as e:
            if attempt == max_retries - 1:
                print(f"Binged API failed after {max_retries} attempts: {e}")
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
    
    return []

async def search_tmdb_api(title, year=None, is_tv=False):
    """Search TMDB API as fallback"""
    try:
        url = TMDB_TV_SEARCH_URL if is_tv else TMDB_SEARCH_URL
        params = {
            'api_key': TMDB_API_KEY,
            'query': title,
            'language': 'en-US'
        }
        
        if year and not is_tv:
            params['year'] = year
        elif year and is_tv:
            params['first_air_date_year'] = year
        
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        
        data = resp.json()
        results = data.get('results', [])
        
        if results:
            movie = results[0]  # Take first result
            return {
                'title': movie.get('title') or movie.get('name'),
                'year': movie.get('release_date', '')[:4] or movie.get('first_air_date', '')[:4],
                'type': 'TV Series' if is_tv else 'Movie',
                'genres': [],  # TMDB requires additional API call for genres
                'languages': [movie.get('original_language', '').upper()],
                'platforms': [{'name': 'Various Platforms'}],
                'overview': movie.get('overview', ''),
                'source': 'tmdb'
            }
    except Exception as e:
        print(f"TMDB API error: {e}")
    
    return None

def create_movie_identifier(title, year):
    """Create unique identifier for movie to prevent duplicates"""
    clean_title = re.sub(r'[^\w]', '', title.lower())
    return f"{clean_title}_{year}"

async def auto_post_movie(client, movie_data, safe_title):
    """Post movie to update channel"""
    try:
        title = clean_text(movie_data.get("title")) or "Unknown"
        year = movie_data.get("theatrical-year") or movie_data.get("year") or "N/A"
        movie_type = clean_text(movie_data.get("type")) or "Movie"
        
        if movie_data.get('source') == 'tmdb':
            genres = movie_data.get('genres', [])
            langs = movie_data.get('languages', ['Unknown'])
            platform_str = movie_data.get('platforms', [{}])[0].get('name', 'Various Platforms')
        else:
            genres = extract_list(movie_data, "genres")
            langs = extract_list(movie_data, "languages")
            platform_str = extract_list(movie_data, "platforms", "name")[0] if extract_list(movie_data, "platforms", "name") else "Various Platforms"
        
        # Use default style (1) for auto-posts
        style = 1
        msg = build_binged_message(
            title, year, movie_type, 
            langs if langs else ["Unknown"], 
            genres, platform_str, style, 
            safe_title, temp.U_NAME
        )
        
        # Post to update channel
        await client.send_message(
            chat_id=UPDATE_CHANNEL,
            text=msg,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔍 Click to Search", url=f"https://t.me/{temp.U_NAME}?start=Search_{safe_title}")]
            ]),
            disable_web_page_preview=True
        )
        
        return True
    except Exception as e:
        print(f"Error posting movie: {e}")
        return False

# AUTO-UPDATE HANDLER
@Client.on_message(filters.document & filters.chat(CHANNELS))
async def auto_update_handler(client, message: Message):
    """Handle new files in database channels and auto-post movie info"""
    try:
        if not message.document or not message.document.file_name:
            return
        
        filename = message.document.file_name
        
        # Extract movie info from filename
        title, year = extract_movie_info_from_filename(filename)
        
        if not title:
            return
        
        # Only process movies from 2025 onwards
        if year and year < 2025:
            return
        
        # Create unique identifier to prevent duplicates
        movie_id = create_movie_identifier(title, year or 2025)
        if movie_id in temp.POSTED_MOVIES:
            print(f"Movie already posted: {title} ({year})")
            return
        
        print(f"Processing: {title} ({year})")
        
        # Search in Binged API first
        search_query = f"{title} {year}" if year else title
        binged_results = await search_binged_api(search_query)
        
        movie_data = None
        
        if binged_results:
            # Filter results by year if specified
            if year:
                year_matched = [r for r in binged_results if str(r.get('theatrical-year', '')) == str(year)]
                if year_matched:
                    movie_data = year_matched[0]
                else:
                    movie_data = binged_results  # Take first result if no year match
            else:
                movie_data = binged_results
        
        # If not found in Binged, try TMDB
        if not movie_data:
            print(f"Not found in Binged, searching TMDB: {title}")
            # Try as movie first
            movie_data = await search_tmdb_api(title, year, is_tv=False)
            
            # If not found as movie, try as TV series
            if not movie_data:
                movie_data = await search_tmdb_api(title, year, is_tv=True)
        
        if movie_data:
            safe_title = re.sub(r'[^a-zA-Z0-9]', '_', title)
            
            # Post to channel
            success = await auto_post_movie(client, movie_data, safe_title)
            
            if success:
                # Mark as posted to prevent duplicates
                temp.POSTED_MOVIES.add(movie_id)
                print(f"Successfully posted: {title} ({year})")
            else:
                print(f"Failed to post: {title} ({year})")
        else:
            print(f"Movie not found in any database: {title} ({year})")
            
    except Exception as e:
        print(f"Error in auto_update_handler: {e}")

# ENHANCED EXISTING COMMANDS (keeping all your original commands with bug fixes)

@Client.on_message(filters.command("setstyle"))
async def set_style(client, message):
    if message.from_user.id not in ADMIN_IDS:
        return await message.reply_text("🚫 You are not authorized.")
    
    if len(message.command) < 2:
        return await message.reply_text(
            "Usage: /setstyle <1-5>\n"
            "Available Styles:\n1. Minimalist\n2. Centered Block\n3. Hashtag Style\n4. Detailed\n5. Instagram-style",
            parse_mode="markdown"
        )
    
    try:
        style = int(message.command[1])
        if style not in range(1, 6): 
            raise ValueError
        temp.BINGED_STYLE[message.from_user.id] = style
        await message.reply_text(f"✅ Style {style} selected.")
    except:
        await message.reply_text("❌ Invalid style number. Use 1–5.")

@Client.on_message(filters.command("binged"))
async def binged_search(client, message):
    if message.from_user.id not in ADMIN_IDS:
        return await message.reply_text("🚫 This command is for admins only.")
    
    if len(message.command) < 2:
        return await message.reply_text("Usage: /binged <movie_name>")
    
    query = " ".join(message.command[1:]).strip()
    
    # Show processing message
    processing_msg = await message.reply_text("🔍 Searching...")
    
    try:
        results = await search_binged_api(query)
        
        if not results:
            return await processing_msg.edit_text("❌ No results found.")
        
        temp.BINGED_RESULTS[message.from_user.id] = {}
        buttons = []
        
        for movie in results[:10]:  # Limit to 10 results
            movie_id = str(movie.get("id", ""))
            if not movie_id:
                continue
                
            title = clean_text(movie.get("title"))
            year = movie.get("theatrical-year") or "N/A"
            btn_text = f"{title} ({year})"[:64]  # Telegram button text limit
            
            temp.BINGED_RESULTS[message.from_user.id][movie_id] = movie
            buttons.append([InlineKeyboardButton(btn_text, callback_data=f"binged_detail_{movie_id}")])
        
        if not buttons:
            return await processing_msg.edit_text("❌ No valid results found.")
        
        buttons.append([InlineKeyboardButton("Close ❌", callback_data="close_message")])
        
        await processing_msg.edit_text(
            f"🎬 Search results for: **{query}**\n\nSelect a movie:",
            reply_markup=InlineKeyboardMarkup(buttons),
            disable_web_page_preview=True
        )
        
    except Exception as e:
        await processing_msg.edit_text(f"❌ Search failed: {str(e)}")

# Enhanced callback handlers with better error handling
@Client.on_callback_query(filters.regex(r"^binged_detail_(\d+)$"))
async def binged_detail(client, cq):
    try:
        movie_id = cq.data.split("_")[-1]
        user_id = cq.from_user.id
        
        movie = temp.BINGED_RESULTS.get(user_id, {}).get(movie_id)
        if not movie:
            return await cq.answer("❌ Session expired. Please search again.", show_alert=True)
        
        title = clean_text(movie.get("title")) or "Unknown"
        year = movie.get("theatrical-year") or "N/A"
        movie_type = clean_text(movie.get("type")) or "N/A"
        genres = extract_list(movie, "genres")
        langs = extract_list(movie, "languages")
        platform_str = extract_list(movie, "platforms", "name")[0] if extract_list(movie, "platforms", "name") else "N/A"
        
        safe_title = re.sub(r'[^a-zA-Z0-9]', '_', title)
        style = temp.BINGED_STYLE.get(user_id, 1)
        
        msg = build_binged_message(
            title, year, movie_type, 
            langs if langs else ["Unknown"], 
            genres, platform_str, style, 
            safe_title, temp.U_NAME
        )
        
        buttons = [[InlineKeyboardButton("🔍 Click to Search", url=f"https://t.me/{temp.U_NAME}?start=Search_{safe_title}")]]
        
        if user_id in ADMIN_IDS:
            buttons.append([
                InlineKeyboardButton("✏️ Edit & Post", callback_data=f"binged_edit_post_{movie_id}"),
                InlineKeyboardButton("📣 Post Default", callback_data=f"binged_post_{movie_id}")
            ])
        
        buttons.append([InlineKeyboardButton("❌ Close", callback_data="close_message")])
        
        await cq.message.reply_text(
            msg, 
            reply_markup=InlineKeyboardMarkup(buttons), 
            disable_web_page_preview=True
        )
        await cq.answer()
        
    except Exception as e:
        await cq.answer(f"❌ Error: {str(e)}", show_alert=True)

# Rest of your existing handlers remain the same...
@Client.on_callback_query(filters.regex(r"^binged_post_(\d+)$"))
async def binged_post(client, cq):
    if cq.from_user.id not in ADMIN_IDS:
        return await cq.answer("You're not authorized.", show_alert=True)
    
    try:
        movie_id = cq.data.split("_")[-1]
        movie = temp.BINGED_RESULTS.get(cq.from_user.id, {}).get(movie_id)
        
        if not movie:
            return await cq.answer("Movie data not found.", show_alert=True)
        
        title = clean_text(movie.get("title")) or "Unknown"
        safe_title = re.sub(r'[^a-zA-Z0-9]', '_', title)
        
        success = await auto_post_movie(client, movie, safe_title)
        
        if success:
            # Add to posted movies to prevent duplicates
            year = movie.get("theatrical-year")
            if year:
                movie_identifier = create_movie_identifier(title, year)
                temp.POSTED_MOVIES.add(movie_identifier)
            await cq.answer("✅ Posted to channel.")
        else:
            await cq.answer("❌ Failed to post.", show_alert=True)
            
    except Exception as e:
        await cq.answer(f"❌ Error: {str(e)}", show_alert=True)

@Client.on_callback_query(filters.regex(r"^binged_edit_post_(\d+)$"))
async def edit_post_prompt(client, cq):
    movie_id = cq.data.split("_")[-1]
    user_id = cq.from_user.id
    temp.EDITING_POST[user_id] = movie_id
    await cq.message.reply_text(
        "✏️ Send the **new search keyword** or **full URL** to use in the search button.", 
        quote=True
    )
    await cq.answer()

@Client.on_message(filters.private & filters.text & filters.user(ADMIN_IDS) & filters.create(lambda _, __, msg: msg.from_user.id in temp.EDITING_POST))
async def receive_custom_search(client, message):
    try:
        user_id = message.from_user.id
        custom_input = message.text.strip()
        
        if user_id not in temp.EDITING_POST:
            return
        
        movie_id = temp.EDITING_POST.pop(user_id)
        movie = temp.BINGED_RESULTS.get(user_id, {}).get(movie_id)
        
        if not movie:
            return await message.reply("❌ Movie session expired. Please search again.")
        
        title = clean_text(movie.get("title")) or "Unknown"
        safe_title = re.sub(r'[^a-zA-Z0-9]', '_', title)
        
        # Create custom button URL
        if custom_input.startswith(("http://", "https://")):
            button_url = custom_input
        else:
            keyword = re.sub(r'[^a-zA-Z0-9]', '_', custom_input)
            button_url = f"https://t.me/{temp.U_NAME}?start=Search_{keyword}"
        
        # Build message
        year = movie.get("theatrical-year") or "N/A"
        movie_type = clean_text(movie.get("type")) or "N/A"
        genres = extract_list(movie, "genres")
        langs = extract_list(movie, "languages")
        platform_str = extract_list(movie, "platforms", "name")[0] if extract_list(movie, "platforms", "name") else "N/A"
        style = temp.BINGED_STYLE.get(user_id, 1)
        
        msg = build_binged_message(
            title, year, movie_type, 
            langs if langs else ["Unknown"], 
            genres, platform_str, style, 
            safe_title, temp.U_NAME
        )
        
        await client.send_message(
            chat_id=UPDATE_CHANNEL,
            text=msg,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔍 Click to Search", url=button_url)]
            ]),
            disable_web_page_preview=True
        )
        
        # Add to posted movies
        movie_identifier = create_movie_identifier(title, year)
        temp.POSTED_MOVIES.add(movie_identifier)
        
        await message.reply("✅ Posted to channel with custom button.")
        
    except Exception as e:
        await message.reply(f"❌ Error: {str(e)}")

@Client.on_callback_query(filters.regex(r"^close_message$"))
async def close_message_callback(client, cq):
    try:
        await cq.message.delete()
    except:
        pass
    await cq.answer()

# ADMIN COMMANDS FOR MANAGING AUTO-UPDATE
@Client.on_message(filters.command("clearposted"))
async def clear_posted_movies(client, message):
    if message.from_user.id not in ADMIN_IDS:
        return await message.reply_text("🚫 You are not authorized.")
    
    temp.POSTED_MOVIES.clear()
    await message.reply_text("✅ Cleared posted movies cache.")

@Client.on_message(filters.command("postedcount"))
async def posted_count(client, message):
    if message.from_user.id not in ADMIN_IDS:
        return await message.reply_text("🚫 You are not authorized.")
    
    count = len(temp.POSTED_MOVIES)
    await message.reply_text(f"📊 Total posted movies: {count}")
