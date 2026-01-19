import re
import html
import asyncio
import aiohttp
from datetime import datetime, timedelta
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from utils import temp
from info import *
from plugins.Extra.binged import HEADERS, ADMIN_IDS, clean_text, find_tmdb_id, get_tmdb_details, search_tmdb_advanced, format_search_title
from database.users_chats_db import db
from TechVJ.bot import TechVJBot
from plugins.Extra.image_gen import generate_status_image
from database.ia_filterdb import get_search_results

# Configuration
UPDATE_CHANNEL_ID = -1001680629032  # Update Channel ID

# Global Cache for Wanted Movies (Movies released but not yet posted)
# Format: {movie_id: movie_data}
WANTED_MOVIES = {}

async def fetch_url(url):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=HEADERS, timeout=10) as response:
                if response.status == 200:
                    return await response.json()
    except Exception as e:
        print(f"Request Error: {e}")
    return None

async def fetch_ottplay_releases(from_date, to_date):
    url = f"https://api2.ottplay.com/api/v4.7/web/new-release?limit=10&from_date={from_date}&to_date={to_date}&content_type=all&language=&provider="
    data = await fetch_url(url)
    if data:
        return data.get('result', [])
    return []

def is_strict_match(title, file_name):
    """
    Checks if the file_name strictly starts with the title.
    Ignores strict punctuation and casing.
    Example: 
      Title: "Him", File: "Him.2026..." -> MATCH
      Title: "Him", File: "Call Him Og..." -> NO MATCH
    """
    if not title or not file_name:
        return False
        
    # Normalize: Replace non-alphanumeric with spaces, lowercase, strip
    def normalize(s):
        return re.sub(r'[\W_]+', ' ', str(s)).lower().strip()
        
    t_clean = normalize(title)
    f_clean = normalize(file_name)
    
    # Must start with title followed by boundary (end of string or space)
    # Pattern: ^title\b
    pattern = r"^" + re.escape(t_clean) + r"\b"
    return bool(re.search(pattern, f_clean))

async def process_and_post_movie(movie, check_db=True):
    """
    Process a single movie: Check if file exists (strict), generate post, send.
    Returns True if posted, False otherwise.
    """
    try:
        movie_id = str(movie.get("_id"))
        title = clean_text(movie.get("name", ""))
        if not title:
            return False
            
        year = movie.get("release_year")
        
        # Double check DB if requested
        if check_db:
             if await db.is_movie_posted(movie_id):
                 # Remove from wanted if already posted
                 if movie_id in WANTED_MOVIES:
                     del WANTED_MOVIES[movie_id]
                 return True

        # Check File Availability with STRICT MATCH
        search_query = f"{title} {year}"
        # Search for files
        files, _, total_files = await get_search_results(UPDATE_CHANNEL_ID, search_query, max_results=20)
        
        found_file = False
        if total_files > 0:
            for file in files:
                # Use file_name if available, else name
                fname = getattr(file, "file_name", None) or getattr(file, "name", "")
                if is_strict_match(title, fname):
                    found_file = True
                    break
        
        if not found_file:
            print(f"Skipping {title} ({year}) - No exact matching file found.")
            return False

        print(f"✅ Found release with available file into DB: {title} ({year})")
        
        # --- Gather Details ---
        content_type = movie.get("content_type", "movie")
        media_type = "movie" if content_type == "movie" else "tv"
        type_str = "Movie" if media_type == "movie" else "Series"
        lang = movie.get("primary_language", {}).get("logo_text", "Unknown")
        genres = [g.get("name") for g in movie.get("genres", [])]
        genre_str = ", ".join(genres) if genres else "N/A"
        
        # Providers
        providers_data = movie.get("where_to_watch", [])
        provider_logos = []
        platform_links = []
        
        for p in providers_data:
            prov = p.get("provider", {})
            p_name = prov.get("name")
            if p_name: 
                # dedupe logic could be here but kept simple
                pass
            logo = prov.get("logo_url") or prov.get("icon_url")
            if logo:
                provider_logos.append(logo)
            
            p_link = p.get("movie_url") or p.get("show_url") or prov.get("seourl")
            if p_link:
                if not p_link.startswith("http"):
                    p_link = f"https://www.ottplay.com/{p_link}"
                platform_links.append(f"[{p_name}]({p_link})")
            elif p_name:
                platform_links.append(p_name)

        provider_str = ", ".join(platform_links[:3]) if platform_links else "N/A"
        
        api_date = movie.get("release_date")
        if api_date:
            try:
                r_date = datetime.fromisoformat(api_date.replace("Z", "+00:00")).strftime("%d-%m-%Y")
            except:
                r_date = api_date
        else:
            r_date = "N/A"

        certs = [c.get("certification") for c in movie.get("certifications", [])]
        cert_str = "/".join(certs) if certs else "N/A"

        posters = movie.get("posters", [])
        ottplay_poster = posters[0] if posters else None
        
        # TMDB Integration
        tmdb_backdrop = None
        tmdb_poster = None
        tmdb_rating = None
        tmdb_plot = None
        tmdb_id = None
        cast_str = "N/A"
        trailer_url = None
        
        tmdb_results = search_tmdb_advanced(title, year=year, media_type=media_type)
        if tmdb_results:
            tmdb_id = tmdb_results[0].get("id")
            tmdb_details = get_tmdb_details(tmdb_id, media_type)
            if tmdb_details:
                tmdb_img = tmdb_details.get("image")
                if tmdb_img: tmdb_backdrop = tmdb_img
                
                t_orig = tmdb_details.get("original_data", {})
                p_path = t_orig.get("poster_path")
                if p_path: tmdb_poster = f"https://image.tmdb.org/t/p/original{p_path}"

                tmdb_rating = tmdb_details.get("rating")
                tmdb_plot = tmdb_details.get("plot")
                cast = tmdb_details.get("cast", [])
                cast_str = ", ".join(cast[:5]) if cast else "N/A"

                videos = tmdb_details.get("videos", [])
                if videos:
                     video_url = videos[0].get("url")
                     if video_url:
                         trailer_url = f"https://www.youtube.com/watch?v={video_url}"

        rating = tmdb_rating if tmdb_rating else (str(movie.get("ottplay_rating")) + "/10" if movie.get("ottplay_rating") else "N/A")
        plot = tmdb_plot if tmdb_plot else "No description available."
        
        safe_title = format_search_title(title, year)
        lang_tag = f"#{lang.replace(' ', '')}"
        
        msg = f"✅ **{title}** · {year} · `{type_str}`\n\n"
        msg += f"**>🉑 {lang_tag}\n"
        msg += f">🎭 {genre_str} · 📺 {provider_str}\n"
        msg += f">®️ {cert_str} · ⭐ {rating}\n"
        msg += f">📅 {r_date}\n"
        msg += f">👥 {cast_str}\n"
        msg += f">\n"
        msg += f">__Plot:__\n"
        msg += f">{plot}**\n"
        msg += f" **@MooviDex** "

        backdrop_url = tmdb_backdrop if tmdb_backdrop else ottplay_poster
        poster_url = ottplay_poster if ottplay_poster else tmdb_poster
        
        final_image_io = None
        if backdrop_url and poster_url:
            print(f"Generating image for {title}...")
            final_image_io = await generate_status_image(
                backdrop_url, poster_url, provider_logos,
                title, year, rating, genre_str, plot
            )

        buttons = []
        if media_type != "tv":
            buttons.append([
                InlineKeyboardButton(
                    f"🔍 Search: {title}", 
                    url=f"https://t.me/{temp.U_NAME}?start=Search_{safe_title}"
                )
            ])
            
        row = []
        if trailer_url:
            row.append(InlineKeyboardButton("🎬 Trailer", url=trailer_url))
        if tmdb_id:
            row.append(InlineKeyboardButton("More like this", callback_data=f"more_like_{tmdb_id}_{media_type}"))
        if row:
            buttons.append(row)

        try:
            if final_image_io:
                await TechVJBot.send_photo(
                    chat_id=UPDATE_CHANNEL_ID,
                    photo=final_image_io,
                    caption=msg,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
            elif backdrop_url:
                await TechVJBot.send_photo(
                    chat_id=UPDATE_CHANNEL_ID,
                    photo=backdrop_url,
                    caption=msg,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
            else:
                await TechVJBot.send_message(
                    chat_id=UPDATE_CHANNEL_ID,
                    text=msg,
                    reply_markup=InlineKeyboardMarkup(buttons),
                    disable_web_page_preview=True
                )
                
            # Mark as posted
            await db.add_posted_movie(movie_id)
            if movie_id in WANTED_MOVIES:
                del WANTED_MOVIES[movie_id]
            
            return True
            
        except Exception as e:
            print(f"Error sending to channel: {e}")
            return False

    except Exception as e:
        print(f"Error processing movie {movie.get('name')}: {e}")
        return False

# Background Loop for Auto-Updates
async def check_releases_loop():
    print("Auto-Update Loop Started (Ottplay v2)")
    await asyncio.sleep(10) 
    
    while True:
        try:
            today = datetime.now()
            from_date = (today - timedelta(days=5)).strftime("%Y-%m-%d")
            to_date = (today + timedelta(days=5)).strftime("%Y-%m-%d")
            
            print(f"Fetching Ottplay releases from {from_date} to {to_date}")
            movies = await fetch_ottplay_releases(from_date, to_date)
            
            if movies:
                for movie in movies:
                    movie_id = str(movie.get("_id"))
                    
                    # If already posted, skip and remove from wanted
                    if await db.is_movie_posted(movie_id):
                        if movie_id in WANTED_MOVIES:
                            del WANTED_MOVIES[movie_id]
                        continue
                        
                    # Add to Wanted List
                    WANTED_MOVIES[movie_id] = movie
                    
                    # Try to process (Check if file already exists)
                    await process_and_post_movie(movie, check_db=False)
                    
                    # Floodwait prevention
                    await asyncio.sleep(2)
            
        except Exception as e:
            print(f"Error in check_releases_loop: {e}")
            
        await asyncio.sleep(3600) # Check every hour

# Immediate Update Handler
@Client.on_message(filters.video | filters.document)
async def check_new_files_available(client, message):
    """
    Listens for new file uploads and checks if they match any Wanted Movies.
    """
    try:
        if not WANTED_MOVIES:
            return

        file_name = None
        if message.video:
            file_name = message.video.file_name
        elif message.document:
            file_name = message.document.file_name
            
        if not file_name:
            return

        # Check against Wanted Movies
        # Use a copy of values to avoid Runtime Error if dictionary changes
        wanted_list = list(WANTED_MOVIES.values())
        
        for movie in wanted_list:
            movie_id = str(movie.get("_id"))
            title = clean_text(movie.get("name", ""))
            
            # Strict match check on the new file name
            if is_strict_match(title, file_name):
                print(f"⚡ Instant Match Found: {file_name} for {title}")
                # Wait a moment for indexing
                await asyncio.sleep(5) 
                
                # Use a lock or check needed? process_and_post_movie handles DB check.
                # Force process
                success = await process_and_post_movie(movie)
                if success:
                    # Notify logic done
                    pass
                break # Matched this file to a movie, move on
                
    except Exception as e:
        print(f"Error in check_new_files_available: {e}")


# More Like This Callback
@Client.on_callback_query(filters.regex(r"^more_like_(\d+)_(.+)$"))
async def more_like_callback(client, cq):
    tmdb_id = cq.matches[0].group(1)
    media_type = cq.matches[0].group(2)
    
    details = get_tmdb_details(tmdb_id, media_type)
    if not details:
        return await cq.answer("Error fetching details", show_alert=True)
        
    similar = details.get("similar", [])
    if not similar:
        return await cq.answer("No similar content found.", show_alert=True)
        
    buttons = []
    for sim in similar[:6]:
        title = sim.get("title") or sim.get("name")
        safe_title = format_search_title(title, None)
        buttons.append([InlineKeyboardButton(f"🔍 {title}", url=f"https://t.me/{temp.U_NAME}?start=Search_{safe_title}")])
        
    buttons.append([InlineKeyboardButton("❌ Close", callback_data="close_message")])
    
    await cq.message.reply_text(f"**More like: {details['title']}**", reply_markup=InlineKeyboardMarkup(buttons))
    await cq.answer()

# /today command
@Client.on_message(filters.command("today"))
async def send_movie_buttons(client, message):
    today = datetime.now().strftime("%Y-%m-%d")
    movies_data = await fetch_ottplay_releases(today, today)

    if not movies_data:
        await message.reply_text("🚫 No new releases found today.")
        return

    buttons = []
    for movie in movies_data[:10]: 
        title = clean_text(movie.get('name', 'No title'))
        movie_id = str(movie.get("_id"))
        callback_data = f"ottplay_detail_{movie_id}"
        buttons.append([InlineKeyboardButton(title, callback_data=callback_data)])

    buttons.append([InlineKeyboardButton("❌ Close", callback_data="close_message")])
    reply_markup = InlineKeyboardMarkup(buttons)

    await message.reply_text(f"🎬 **Releases for {today}:**", reply_markup=reply_markup)

# Callback for Ottplay details
@Client.on_callback_query(filters.regex(r"^ottplay_detail_(.+)$"))
async def ottplay_detail(client, cq):
    movie_id = cq.data.split("_")[-1]
    
    today = datetime.now().strftime("%Y-%m-%d")
    movies = await fetch_ottplay_releases(today, today)
    
    movie = next((m for m in movies if str(m.get("_id")) == movie_id), None)
    if not movie:
         return await cq.answer("Movie details not found.", show_alert=True)

    title = clean_text(movie.get("name", ""))
    year = movie.get("release_year")
    content_type = movie.get("content_type", "movie")
    media_type = "movie" if content_type == "movie" else "tv"
    type_str = "Movie" if media_type == "movie" else "Series"
    lang = movie.get("primary_language", {}).get("logo_text", "Unknown")
    genres = [g.get("name") for g in movie.get("genres", [])]
    genre_str = ", ".join(genres) if genres else "N/A"
    
    providers_data = movie.get("where_to_watch", [])
    provider_logos = []
    platform_links = []
    
    for p in providers_data:
        prov = p.get("provider", {})
        p_name = prov.get("name")
        logo = prov.get("logo_url") or prov.get("icon_url")
        if logo: provider_logos.append(logo)
        p_link = p.get("movie_url") or p.get("show_url") or prov.get("seourl")
        if p_link:
             if not p_link.startswith("http"): p_link = f"https://www.ottplay.com/{p_link}"
             platform_links.append(f"[{p_name}]({p_link})")
        elif p_name: platform_links.append(p_name)
    provider_str = ", ".join(platform_links[:3]) if platform_links else "N/A"
    
    api_date = movie.get("release_date")
    if api_date:
        try: r_date = datetime.fromisoformat(api_date.replace("Z", "+00:00")).strftime("%d-%m-%Y")
        except: r_date = api_date
    else: r_date = "N/A"

    certs = [c.get("certification") for c in movie.get("certifications", [])]
    cert_str = "/".join(certs) if certs else "N/A"
    posters = movie.get("posters", [])
    ottplay_poster = posters[0] if posters else None
    
    tmdb_backdrop, tmdb_poster, tmdb_rating, tmdb_plot, tmdb_id = None, None, None, None, None
    cast_str = "N/A"
    
    tmdb_results = search_tmdb_advanced(title, year=year, media_type=media_type)
    if tmdb_results:
        tmdb_id = tmdb_results[0].get("id")
        tmdb_details = get_tmdb_details(tmdb_id, media_type)
        if tmdb_details:
            tmdb_img = tmdb_details.get("image")
            if tmdb_img: tmdb_backdrop = tmdb_img
            t_orig = tmdb_details.get("original_data", {})
            p_path = t_orig.get("poster_path")
            if p_path: tmdb_poster = f"https://image.tmdb.org/t/p/original{p_path}"
            tmdb_rating = tmdb_details.get("rating")
            tmdb_plot = tmdb_details.get("plot")
            cast = tmdb_details.get("cast", [])
            cast_str = ", ".join(cast[:5]) if cast else "N/A"
            
    rating = tmdb_rating if tmdb_rating else (str(movie.get("ottplay_rating")) + "/10" if movie.get("ottplay_rating") else "N/A")
    plot = tmdb_plot if tmdb_plot else "No description available."
    safe_title = format_search_title(title, year)
    lang_tag = f"#{lang.replace(' ', '')}"
    
    msg = f"✅ **{title}** · {year} · `{type_str}`\n\n"
    msg += f"**>🉑 {lang_tag}\n"
    msg += f">🎭 {genre_str} · 📺 {provider_str}\n"
    msg += f">®️ {cert_str} · ⭐ {rating}\n"
    msg += f">📅 {r_date}\n"
    msg += f">👥 {cast_str}\n"
    msg += f">\n"
    msg += f">__Plot:__\n"
    msg += f">{plot}**\n"
    msg += f" **@MooviDex** "
    
    backdrop_url = tmdb_backdrop if tmdb_backdrop else ottplay_poster
    poster_url = ottplay_poster if ottplay_poster else tmdb_poster
    
    final_image_io = None
    if backdrop_url and poster_url:
        await cq.answer("Generating image...", cache_time=0)
        final_image_io = await generate_status_image(backdrop_url, poster_url, provider_logos, title, year, rating, genre_str, plot)
    
    buttons = [[InlineKeyboardButton(f"🔍 Search: {title}", url=f"https://t.me/{temp.U_NAME}?start=Search_{safe_title}")]]
    buttons.append([InlineKeyboardButton("❌ Close", callback_data="close_message")])
    
    if final_image_io:
        await cq.message.reply_photo(photo=final_image_io, caption=msg, reply_markup=InlineKeyboardMarkup(buttons))
    elif backdrop_url:
        await cq.message.reply_photo(photo=backdrop_url, caption=msg, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await cq.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(buttons), disable_web_page_preview=True)
    await cq.answer()

@Client.on_callback_query(filters.regex(r"close_message"))
async def close_message_callback(client, callback_query):
    try: await callback_query.message.delete()
    except Exception: await callback_query.answer("⚠️ Unable to delete the message.")

asyncio.create_task(check_releases_loop())
